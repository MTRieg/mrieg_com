This is the code to my website, which if you're reading this message should be available at mrieg.com. 

The things that I have established that were not included with this github repo are:
cloudflare account, tunnels, DNS records showing that I own mrieg.com, etc
Startup scripts that call start.sh with various combinations of flags
A computer running Linux Mint to run the server. (hence why start.sh creates xfce4 terminals)
  (yes, there are more efficient linux distros, but I still want there to be a usable ui in the os, even for the server)
node packages, python libraries, docker, and other code that needs to be installed from their source.
  (some of them happen automatically with the build flag)

## Local Testing (Linux)

For first-time setup on any Linux computer:

### Prerequisites
1. **Docker and Docker Compose** - Install via your package manager:
   ```bash
   sudo apt update
   sudo apt install docker.io docker-compose
   sudo usermod -aG docker $USER  # Then log out and back in
   ```

2. **Git** (to clone the repo):
   ```bash
   sudo apt install git
   ```

### Running the Server

1. Clone and navigate to the project:
   ```bash
   git clone <your-repo-url>
   cd Mrieg_com_fastAPI_v0_3
   ```

2. Start all services (first run will build the Docker images):
   ```bash
   docker-compose up --build
   ```
   
   For subsequent runs, you can omit `--build`:
   ```bash
   docker-compose up
   ```

3. Access the site at: `http://localhost:8000/games/knockout`

### Stopping the Server
```bash
docker-compose down
```

### Notes
- The Docker build handles Python dependencies (requirements.txt) and Node.js automatically
- Data is stored in a SQLite database (`dev.db`) and Redis
- To reset all data, delete `dev.db` and `schedule.db` and run `docker volume rm redis_data` before starting


