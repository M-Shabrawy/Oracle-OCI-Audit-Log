## Oracle-OCI-Audit-Log
Python Script to collect Oracle Cloud Audit log

#Generate Private Key
openssl genrsa -out oci_api_key.pem -aes128 2048

Enter Password

#Generate Public Key
openssl rsa -pubout -in oci_api_key.pem -out oci_api_public_key.pem

Enter PrivKey Password

#Get Key Fingerprin
openssl rsa -pubout -outform DER -in oci_api_key.pem | openssl md5 -c

openssl rsa -in oci_api_key.pem -out oci_api_key.dec


