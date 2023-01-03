#!/usr/bin/env bash
# Define where to store the generated certs and metadata.
DIR="$(pwd)/.certs"

SERVICES_NAMES=device-manager

rm -rf $DIR
mkdir -p $DIR

# Create the openssl configuration file. This is used for both generating
# the certificate as well as for specifying the extensions. It aims in favor
# of automation, so the DN is encoding and not prompted.
cat >"${DIR}/openssl.cnf" <<EOF
####################################################################
[ ca ]
default_ca = CA_default        # The default ca section

[ CA_default ]
default_md  = sha256            # use public key default MD
preserve    = no                # keep passed DN ordering

x509_extensions = ca_extensions # The extensions to add to the cert

email_in_dn = no                # Don't concat the email in the DN
copy_extensions = copy          # Required to copy SANs from CSR to cert

####################################################################
[ req ]
default_bits        = 2048
default_keyfile     = tmp/external.key
distinguished_name  = ca_distinguished_name
x509_extensions     = ca_extensions
string_mask         = utf8only

####################################################################
[ ca_distinguished_name ]
countryName                    = BR
stateOrProvinceName            = PB
localityName                   = Campina Grande
organizationName               = HANIoT
organizationalUnitName         = HANIoT
commonName                     = HANIoT CA

####################################################################
[ ca_extensions ]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always, issuer
basicConstraints = critical, CA:true
keyUsage = critical, digitalSignature, nonRepudiation, keyCertSign, cRLSign

####################################################################
[ client_extensions ]
basicConstraints = CA:false
keyUsage         = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
subjectAltName   = @alt_names

####################################################################
[ server_extensions ]
basicConstraints = CA:false
keyUsage         = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName   = @alt_names
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer

####################################################################
[ client_server_extensions ]
basicConstraints     = CA:FALSE
keyUsage             = digitalSignature, keyEncipherment
extendedKeyUsage     = clientAuth, serverAuth
subjectKeyIdentifier = hash
subjectAltName       = @alt_names

####################################################################

[ alt_names ]
IP.1  = 127.0.0.1
DNS.1 = localhost
EOF

# Create the certificate authority (CA). This will be a self-signed CA, and this
# command generates both the private key and the certificate. You may want to
# adjust the number of bits (4096 is a bit more secure, but not supported in all
# places at the time of this publication).
#
# To put a password on the key, remove the -nodes option.
#
# Be sure to update the subject to match your organization.
#
# Generate your CA certificate
openssl req -x509 \
  -config "$DIR/openssl.cnf" \
  -nodes -days 3650 \
  -subj "/O=HANIoT,CN=HANIoT CA" \
  -keyout "$DIR/ca.key" \
  -out "$DIR/ca.pem" 2>/dev/null

# Params:
# type (server, client) $1, CN $2, Alt Names $3, filename $4, output $5
generateCerts() {
  # Create destination directory
  mkdir -p $5

  ORG="$2"
  TYPE="server_extensions"

  if [ "$1" = "client" ]; then
    TYPE="client_extensions"
  elif [ "$1" = "client/server" ]; then
    TYPE="client_server_extensions"
  fi

  # Add Subject Alternative Names
  DNS_LIST=$(echo $3 | sed "s/,/ /g")
  NUMBER=2
  for DNS in ${DNS_LIST}; do
    echo "DNS.${NUMBER} = ${DNS}" >>$DIR/openssl.cnf
    NUMBER=$((NUMBER + 1))
  done

  # Generate the private key
  openssl genrsa -out "$5/$4_key.pem" 2>/dev/null

  # Generate a CSR using the configuration and the key just generated. We will
  # give this CSR to our CA to sign.
  openssl req \
    -new -nodes \
    -key "$5/$4_key.pem" \
    -subj "/O=$ORG/CN=HANIoT" \
    -out "$5/$4.csr" 2>/dev/null

  # Sign the CSR with our CA. This will generate a new certificate that is signed
  # by our CA.
  openssl x509 \
    -req -days 3650 -in "$5/$4.csr" \
    -CA "$DIR/ca.pem" -CAkey "$DIR/ca.key" -CAcreateserial \
    -out "$5/$4_cert.pem" -extfile "$DIR/openssl.cnf" \
    -extensions $TYPE 2>/dev/null

  # Copy CA file to the destination directory
  cp "$DIR/ca.pem" "$5/ca.pem"

  chmod 0644 "$DIR/ca.pem" "$5/$4_key.pem" "$5/$4_cert.pem"

  # Remove unused files
  rm -f $5/*.csr
}

# type (server, client) $1, CN $2, Alt Names $3, filename $4, output $5
generateCertsMongo() {
  generateCerts $1 $2 $3 $4 $5
  cat "$5/$4_cert.pem" "$5/$4_key.pem" >"$5/$4.pem"
  rm -f "$5/$4_cert.pem" "$5/$4_key.pem"
}

# Certificates for microservices
SERVICES_ALT_NAMES_MONGO="mongo"
SERVICES=$(echo $SERVICES_NAMES | tr "," "\n")
COUNT=${#SERVICES[@]}
for service in ${SERVICES[@]}; do
  SERVICES_ALT_NAMES_MONGO+=",mongo-${service}"
  echo "$COUNT - Generating certificates for the \"${service^^}\" Service..."
  generateCerts "server" "$service" "localhost" "server" "$DIR/$service"  # Server
  generateCerts "client" "$service" "rabbitmq" "rabbitmq" "$DIR/$service" # Client RabbitMQ

  if [ "$service" = "timeseries" ]; then
    generateCerts "client" "$service" "influxdb" "influxdb" "$DIR/$service" # Client InfluxDB
  else
    generateCertsMongo "client" "$service" "mongo,${service}" "mongodb" "$DIR/$service" # Client MongoDB
  fi

  if [ "$service" = "device-manager" ]; then
    # Create JWT certs
    ssh-keygen -t rsa -P "" -b 2048 -m PEM -f "$DIR/$service/jwt.key"
    ssh-keygen -e -m PEM -f "$DIR/$service/jwt.key" >"$DIR/$service/jwt.key.pub"
  fi
  COUNT=$((COUNT + 1))
done

# Generate certificates for MongoDB
echo "$COUNT - Generating certificates for the \"MongoDB Server\"..."
generateCertsMongo "server" "mongo" $SERVICES_ALT_NAMES_MONGO "server" "$DIR/mongodb" # Server MongoDB

# Generate certificates for RabbiMQ
generateCerts "server" "rabbitmq" "rabbitmq" "server" "$DIR/rabbitmq" # Server RabbitMQ

## Generate certificates for InfluxDB
#echo "$((COUNT + 3)) - Generating certificates for the \"InfluxDB Server\"..."
#generateCerts "server" "influxdb" "influxdb,influxdb-timeseries" "server" "$DIR/influxdb" # Server InfluxDB

# (Optional) Remove unused files at the moment
rm -rf $DIR/ca.* $DIR/*.srl $DIR/*.csr $DIR/*.cnf
