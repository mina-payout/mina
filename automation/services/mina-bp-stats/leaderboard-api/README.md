## Leaderboard Bot  
Initial config for Leaderboard API  
  
  
## DB Config:   
	Install postgres   
	Execute SQL statement from database\tables.sql. This will create tables and initial config data needed by bot.  
	In config.py update below properties (All properties are required):  
	`POSTGRES_HOST`			The postgres hostname  
    `POSTGRES_PORT`			The postgres port  
    `POSTGRES_USER`			The postgres username  
    `POSTGRES_PASSWORD`		The postgres password  
    `POSTGRES_DB`			The postgres  database name  
	
	**Note**  If postgres is hosted on different machine, make sure to update "postgresql.conf" 
		and set  "listen_addresses" to appropriate value.  
	  

## Setup the env-file
1.Add all required credential value to file as key-value pair.Review the config_variables.env file. 
2.Provide this .env file while running the docker run command.

### Installing Docker file
1. Go to the terminal.
2. Type belowe Commands.
3. * >cd leaderboard-bot
   * >docker build -t leaderborad-api .
   * >docker run --env-file config_variables.env -i -t leaderborad-api:latest
    
For docker, please update all above propeties also copy the credetials file in same folder as 	  
	  
	