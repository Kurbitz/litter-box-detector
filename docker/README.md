#### Installing Docker and Docker Compose
Getting Docker up and running on Ubuntu is very easy. You can find instructions on how to do it [here](https://docs.docker.com/engine/install/ubuntu/). Once you've installed Docker you'll need to install Docker Compose. You can find instructions on how to do that [here](https://docs.docker.com/compose/install/).

#### Setting up the server stack
Once you've installed Docker and Docker Compose you're ready to set up the server stack. You can find the Docker Compose files in the GitHub-repository. 

The stack is split up into three different Docker Compose files. One for the Mosquitto, one for the TIG-stack and one for Node-RED. This is done so that I can easily tear down and rebuild the TIG-stack without having to rebuild the entire stack. This is useful when I want to make changes to one part of the stack without having to rebuild the entire thing, cutting down on downtime. To assist other people in setting up the stack I plan on creating a script that will automatically pull the latest version of the stack from GitHub and set it up. I'll update this section once I've done that.

To set up the stack you'll either need to clone the GitHub-repository or create the directory structure manually. If creating the directory structure manually you'll need to copy the files from the GitHub-repository into the correct directories.
The directory structure should look something like this:
```
├── mosquitto
│   ├── data
│   ├── log
│   ├── config
│   │   ├── password.txt
│   │   └── mosquitto.conf
│   └── docker-compose.yml
├── nodered
│   ├── data
│   └── docker-compose.yml
└── tig-stack
    ├── telegraf
    │   └── telegraf.conf
    ├── entrypoint.sh
    ├── .env
    └── docker-compose.yml
```

Once you've set up the directory structure you can start each part of the stack by running: 
```
docker-compose up -d
```

The ```-d``` flag tells Docker Compose to run the containers in the background. If you want to see the logs from the containers in your shell you can omit the ```-d``` flag.

#### Configuration
The configuration files for each part of the stack can be found in the GitHub-repository. You'll need to make a few changes to the configuration files before you can start the stack.

##### Mosquitto
In the mosquitto directory you'll find a mosquitto.conf file. This is the configuration file for Mosquitto. You'll need to change the ```allow_anonymous``` setting to ```false``` and uncomment the ```password_file``` setting. Run the following command to generate a password file:

```bash
docker compose exec mosquitto mosquitto_passwd -b /mosquitto/config/password.txt user password
docker compose restart mosquitto
```
With "user" and "password" being the username and password you want to use. You can change these to whatever you want. Just make sure to change them in the NodeMCU code as well.

Mosquitto will start on port 1883 by default. If you want to change this you'll need to change the ```ports``` setting in the docker-compose.yml file.

##### TIG-stack
Change the variables with the ```CHANGE_ME``` placeholder in the .env file to whatever you want. You can leave the rest of the variables as they are.

Influx will start on port 8086 by default and Grafana will start on port 3000. If you want to change this you'll need to change the ports defined in the .env file.

#### Node-RED
Node-RED needs basically no configuration. You can access the Node-RED editor by going to ```http://<server-ip>:1880``` in your browser. You can find more information on how to use Node-RED [here](https://nodered.org/docs/user-guide/).
