import datetime
import oci
import shutil
import os
from oci.config import validate_config

base_path = "D:\oci"
audit_file_name = "oci.aud"
state_file_name = ".state"
log_file_name = "D:\oci\out.log"
history_minutes = -1440 # 1 Day Default
max_log_file_size_bytes = 52428800 # 50MB Default

def get_subscription_regions(identity, tenancy_id):
    '''
    To retrieve the list of all available regions.
    '''
    list_of_regions = []
    list_regions_response = identity.list_region_subscriptions(tenancy_id)
    for r in list_regions_response.data:
        list_of_regions.append(r.region_name)
    return list_of_regions


def get_compartments(identity, tenancy_id):
    '''
    Retrieve the list of compartments under the tenancy.
    '''
    list_compartments_response = oci.pagination.list_call_get_all_results(
        identity.list_compartments,
        compartment_id=tenancy_id).data

    compartment_ocids = [c.id for c in filter(lambda c: c.lifecycle_state == 'ACTIVE', list_compartments_response)]

    return compartment_ocids


def get_audit_events(audit, compartment_ocid, start_time, end_time):
    '''
    Get events iteratively for each compartment defined in 'compartments_ocids'
    for the region defined in 'audit'.
    This method eagerly loads all audit records in the time range and it does
    have performance implications of lot of audit records.
    Ideally, the generator method in oci.pagination should be used to lazily
    load results.
    '''
    list_of_audit_events = []
    list_events_response = oci.pagination.list_call_get_all_results(
        audit.list_events,
        compartment_id=compartment_ocid,
        start_time=start_time,
        end_time=end_time).data

    #  Results for a compartment 'c' for a region defined
    #  in 'audit' object.
    list_of_audit_events.extend(list_events_response)
    return list_of_audit_events

def check_path(base_file_path):
    if os.path.isdir(base_file_path):
            write_log(log_file_name,"Output directory %s exists" % base_file_path)
    else:
        try:
            os.makedirs(base_file_path)
        except OSError:
            write_log(log_file_name,"Error Creating Output Directory %s" % base_file_path)
        else:
            write_log(log_file_name,"Successfully created Output Directory %s" % base_file_path)
            
def get_state(state_file):
    #Check if state file exists and return state timestamp else return 15 minutes form now!
    if os.path.isfile(state_file):
        sf = open(state_file,"r")
        state_date = sf.read()
        sf.close
        if state_date == '':
            return datetime.datetime.utcnow() + datetime.timedelta(minutes=history_minutes)
        return datetime.datetime.strptime(state_date, '%Y-%m-%d %H:%M:%S.%f%z')
    else:
        return datetime.datetime.utcnow() + datetime.timedelta(minutes=history_minutes)
        
        
def cleanup_log(file_name, max_size):
    try:
        if os.path.isfile(file_name):
            s = os.path.getsize(file_name)
            if s > max_size:
                os.remove(file_name)
            else:
                print("Log File Size {0}".format(s))
    except OSError as err:
        write_log(log_file_name,"File Error {0}" .format(err))


def write_log(log_file_name,message):
    msg = str(datetime.datetime.utcnow()) + ": " + message + "\n"
    try:
        cleanup_log(log_file_name,max_log_file_size_bytes)
        lf = open(log_file_name,"a")
        lf.write(msg)
        lf.close
    except OSError as err:
        print ("Log file error {0}".format(err))
        

def main():
    try:    
        # Check Base path exists
        check_path(base_path)
        config = oci.config.from_file("./config.txt","DEFAULT")
        validate_config(config)
        tenancy_id = config["tenancy"]
        # Initialize CLient
        identity = oci.identity.IdentityClient(config)
        #Start as current UTC Time
        end_time = datetime.datetime.utcnow()
        
        #Subscription Regions
        regions = get_subscription_regions(identity, tenancy_id)
        write_log(log_file_name,"Found {0!s} Regions in Tenant {1}".format(len(regions),tenancy_id))
        #Get Compartments
        compartments = get_compartments(identity, tenancy_id)
        write_log(log_file_name,"Found {0!s} Compartments in Tenant {1}".format(len(compartments),tenancy_id))
        #Initialize audit client
        audit = oci.audit.audit_client.AuditClient(config) 
        
        for r in regions:
            #  Intialize with a region value.
            audit.base_client.set_region(r)
            # Set and validate base path for region
            region_base_file_path = base_path + "\\" + r
            
            check_path(region_base_file_path)
            
            for c in compartments:
                state = ""
                #Set State and Log file paths
                audit_file = region_base_file_path  + "\\" + c + audit_file_name
                state_file = region_base_file_path  + "\\" + c + state_file_name
                # Get events` start time
                start_time = get_state(state_file)
                # Cleanup log file
                cleanup_log(audit_file,max_log_file_size_bytes)
                #Get Compartment Audit log
                audit_events = get_audit_events(
                    audit,
                    c,
                    start_time,
                    end_time)
                write_log(log_file_name,"Found {0!s} Events in CompartmentID {1} Region {2}".format(len(audit_events),c,r))
                
                if audit_events:
                    of = open(audit_file,"a")
                    for e in audit_events:
                        record = str(e.event_time) + ",compartment_name=" + str(e.data.compartment_name) + ",principal_name=" + str(e.data.identity.principal_name) + ",ip_address=" + str(e.data.identity.ip_address) + ",event_name=" + str(e.data.event_name) + ",source=" + str(e.source) + ",request.action=" + str(e.data.request.action) + ",response.status=" + str(e.data.response.status) + ",response.message=" + str(e.data.response.message) + "\n"
                        of.write(record)
                        #Get last event timestamp and write to state
                        state = str(e.event_time)
                    if state == "":
                        write_log(log_file_name,"Null state error for Compartment {0}".format(c))
                    else:
                        sf = open(state_file,"w")
                        sf.write(state)
                        sf.close
                    of.close
                else:
                    print("No audit for Compartment {0}".format(c))
                
    except OSError as err:
        write_log(log_file_name,"OS Error {0}" .format(err))
    except ValueError:
        write_log(log_file_name,"Could not convert data.")
    except:
        write_log(log_file_name,"Unexpected error: {0}".format(sys.exc_info()[0]))
        raise

if __name__ == "__main__":
    main()