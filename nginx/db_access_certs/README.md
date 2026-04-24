Files required for PostgreSQL mTLS on `5432`:

- `ca.crt` - CA certificate used to verify allowed client certificates.
- `server.crt` - server certificate presented by Nginx stream endpoint on `5432`.
- `server.key` - private key for `server.crt`.

The Nginx container mounts this directory as `/etc/db_access_certs`.

# Generate certificates

1. Generate CA key and certificate:

```sh
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt -subj "/CN=opinion-bot-db-ca"
```

2. Generate server key and CSR:

```sh
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/CN=<db-hostname>"
```

3. Sign server certificate with SAN for your DB hostname:

```sh
cat > server.ext <<'EOF'
subjectAltName=DNS:<db-hostname>
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 825 -sha256 -extfile server.ext
```

4. Generate a client key and CSR:

```sh
openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr -subj "/CN=<client-name>"
```

5. Sign client certificate:

```sh
cat > client.ext <<'EOF'
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAserial ca.srl -out client.crt -days 825 -sha256 -extfile client.ext
```

6. Keep in this directory:
- `ca.crt`
- `server.crt`
- `server.key`

7. Distribute to each approved client:
- `client.crt`
- `client.key`
- `ca.crt`

8. Remove temporary files after issuance:

```sh
rm -f ca.key ca.srl server.csr server.ext client.csr client.ext
```

# Revocation / rotation workflow

- If one client is compromised, rotate that client cert/key.
- If CA trust is compromised, rotate `ca.crt`, reissue all client certs, and reload Nginx.

Test with psql:

```sh
psql "host=<server> port=5432 dbname=<db> user=<user> sslmode=verify-full sslrootcert=ca.crt sslcert=client.crt sslkey=client.key"
```
