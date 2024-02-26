# Mina Leaderboard 
### Technologies Used 
***
> Postgresql,
> Html 5,
> Bootstrap 4, 
> Php 8.0,
> Docker
***

## How to change IP address for Leader board UI

***

### Create SSL certificate 
1. Copy `mkcert-v1.4.3-linux-amd64` file from web-dev folder to your home directory.
2. Type belowe Commands.
   * >chmod +x mkcert-v1.4.3-linux-amd64
   * >./mkcert-v1.4.3-linux-amd64 -install
   * >./mkcert-v1.4.3-linux-amd64 < Host Address name > < your Host Mina Network IP Address > ::1
   * > e.g. `./mkcert-v1.4.3-linux-amd64 mina-project.info 172.16.238.10 ::1`

3. In home directory two files genrated with names `mina-project.info+2.pem` and `mina-project.info+2-key.pem`.
4. Copy this both files in `web-dev/php/SSL`.
5. Rename `mina-project.info+2.pem` with `cert.pem`.
6. Rename `mina-project.info+2-key.pem` with `cert-key.pem`.
***
## Installing Docker file
1. Download / Move WEB-DEV folder, to home directory in ubuntu.
2. 1. > Create a config file with below paramerters: 
##### DB_SIDECAR_HOST=
##### DB_SIDECAR_PORT=
##### DB_SIDECAR_USER=
##### DB_SIDECAR_PWD=
##### DB_SIDECAR_DB=
##### DB_SNARK_HOST=
##### DB_SNARK_PORT=
##### DB_SNARK_USER=
##### DB_SNARK_PWD=
##### DB_SNARK_DB=
##### API_HOST=

>configure these variables and save the file.
3. Go to the terminal.
4. Type belowe Commands.
5. * >cd web-dev/php
   * >docker build -t mina-web .
### It will install all dependancies and start the container .After finishing the process we will opening the browser with `172.16.238.10`
***

### Note
After Any changes in project you have rebuild the docker file by using 
`docker build -t mina-web .`
this command and again run the container .
