---
layout: default
title: Custom Client Certificates
parent: Articles
nav_order: 1
---

# Configuring client-server certificates


## Create a certificate
We need a certificate signed by a CA, the server will provide it on any request. We on the client side will "trust" with the CA certificate.

### CA

* Generate private key

```sh
openssl genrsa -out ca.key 4096
```

* create ca.cnf file:

```ini
[ req ]
default_bits       = 4096
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_ca

[ dn ]
C  = ES
ST = Galicia
L  = Vilalba
O  = mandrewcito Corp
OU = Development
CN = localhost

[ v3_ca ]
basicConstraints = critical, CA:TRUE
keyUsage = critical, digitalSignature, cRLSign, keyCertSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer

```

* Generate root certificate

```sh
openssl req \
  -new \
  -x509 \
  -days 3650 \
  -key ca.key \
  -out ca.crt \
  -config ca.cnf

```
* verify certificate

```sh
openssl x509 -in ca.crt -noout -text
```
### Create server certificate

* Generate private key

```sh
openssl genrsa -out localhost.key 2048
```

* CSR with SAN, create localhost.cnf file:
```ini
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = req_ext

[ dn ]
C  = ES
ST = Galicia
L  = Local
O  = Desarrollo
OU = Dev
CN = localhost

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = localhost
IP.1  = 127.0.0.1
IP.2  = ::1

```
* Generate CSR:
```sh
openssl req \
  -new \
  -key localhost.key \
  -out localhost.csr \
  -config localhost.cnf
```
* Server certificate extensions server.ext
```ìni
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = localhost
IP.1  = 127.0.0.1
IP.2  = ::1
```

* Sign server with CA:
```sh
openssl x509 \
  -req \
  -in localhost.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out localhost.crt \
  -days 825 \
  -sha256 \
  -extfile server.ext
```
* verify trust chain:

```sh
openssl verify -CAfile ca.crt localhost.crt
```
#### Krestel certificate (netcore server)

```sh
openssl pkcs12 -export \
  -out localhost.pfx \
  -inkey localhost.key \
  -in localhost.crt \
  -name kestrel-cert
```
> password: signalrcore


## Configuring server side

Copy certificate (.pfx) on code folder and include it into the solution, add to your krestel the following env variables:

```dockerfile
# ... #
ENV ASPNETCORE_Kestrel__Certificates__Default__Password=signalrcore
ENV ASPNETCORE_Kestrel__Certificates__Default__Path=localhost.pfx
# ... #
```
sample server code [here](https://github.com/mandrewcito/signalrcore-containertestservers/tree/main/src/SignalRSampleServer)

## Client side
### Install CA certificate (depends on OS example is debian/ubuntu)
> this step is optional
```sh
sudo cp ca.crt /usr/local/share/ca-certificates/my-ca-local.crt
sudo update-ca-certificates
```

Check certificate:

```sh
trust list | grep "Mi CA Local"
```

### check with requests

```python
import requests
>>> requests.get("http://localhost:5000")
<Response [200]>
>>> requests.get("https://localhost:5001", verify="ca.crt")
<Response [200]>
>>> requests.get("https://localhost:5001")
raise SSLError(e, request=request)
requests.exceptions.SSLError: HTTPSConnectionPool(host='localhost', port=5001): Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)')))
```

> now you can take a look to certificates_test.py, here you can see how configure properly ssl_context.
> 
> Have fun :)