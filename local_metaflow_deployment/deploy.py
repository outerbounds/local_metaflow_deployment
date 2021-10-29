import os
import docker
import tempfile
import time
from docker.errors import NotFound

DEPLOYMENT_NAMING_PREFIX = 'mfdeploy'
DEFAULT_NETWORK_NAME = 'metaflow-deployment-netwok'
MD_SERVICE_VERSION = [
"1.0.0"
"1.0.1"
"2.0.4"
"2.0.5"
"2.0.6"
"2.1.0"
]
UI_VERSIONS = [
    'v1.0.0',
    'v1.0.1'
]
POSTGRES_IMAGE = 'postgres:latest'
MF_UI_REPO = 'git@github.com:Netflix/metaflow-ui.git'
MF_MD_REPO = 'git@github.com:Netflix/metaflow-service.git'
NO_DEPLOYMENT_FOUND = "No Containers found for deployment. Run `create` command to create a new deployment"

class IpNotResolved(Exception):
    headline = 'IP Address of Container Unresolvable'
    def __init__(self, container_name='',container_id='', lineno=None):
        self.message = f"Cannot Resolve IP Address of containers/network : {container_name} : {container_id}"
        self.line_no = lineno
        super(IpNotResolved, self).__init__()

class ExistingDeploymentException(Exception):
    headline = 'One deployment Already Exists'
    def __init__(self,container_names):
        self.message = f"Deployment Already exists with containers : {', '.join(container_names)}. Please run the `teardown` command before creating a new deployment"
        super(ExistingDeploymentException, self).__init__()

class NetworkNotFound(Exception):
    headline = 'Cannot Find Network'
    def __init__(self, network_name=''):
        self.message = f"Cannot Find Network : {network_name}"
        super(NetworkNotFound, self).__init__()

class DeployDockerMetalflow:

    def __init__(self,
                database_name='metaflow',
                database_password='password',
                database_user='metaflow',
                database_port = 5432,
                logger=None,
                network_name=DEFAULT_NETWORK_NAME,
                metadata_repo_version='2.1.0',
                ui_version='1.0.0',
                max_ip_wait_time = 20,\
                metadata_port = 8080,
                ui_port = 3000,
                ui_service_port = 8083,
                migration_port = 8082,
                ):
        
        self._docker = docker.DockerClient(base_url='unix://var/run/docker.sock')

        self._logger = logger if logger is not None else lambda *args:print(*args)
        # Network Related Properties
        self._network = None
        self._network_name = network_name

        # database related configurations.
        self._database_container = None
        self._database_container_name = 'postgres'
        self._database_name = database_name
        self._database_password = database_password
        self._database_user = database_user
        self._database_port = database_port
        self._max_ip_wait_time = max_ip_wait_time

        # Configuration related to the containers for the test harness. 
        self._metadata_version = metadata_repo_version
        self._ui_version = ui_version
        self._ui_service_container_name = 'ui-service'
        self._ui_container_name = 'ui'
        self._metadata_service_container_name = 'metadata-service'
        self._metadata_port = metadata_port
        self._ui_port = ui_port
        self._ui_service_port = ui_service_port
        self._migration_port =migration_port

        self._ui_tempdir = tempfile.TemporaryDirectory(prefix='mf-gui')
        self._md_tempdir = tempfile.TemporaryDirectory(prefix='mf-metadata')
        
        
        
    
    @property
    def database_container_name(self):
        return f'{DEPLOYMENT_NAMING_PREFIX}-{self._database_container_name}'

    @property
    def ui_service_container_name(self):
        return f'{DEPLOYMENT_NAMING_PREFIX}-{self._ui_service_container_name}'
    
    @property
    def ui_container_name(self):
        return f'{DEPLOYMENT_NAMING_PREFIX}-{self._ui_container_name}'

    @property
    def metadata_service_container_name(self):
        return f'{DEPLOYMENT_NAMING_PREFIX}-{self._metadata_service_container_name}'
    
    @property
    def network_name(self):
        return f'{DEPLOYMENT_NAMING_PREFIX}-{self._network_name}'
    
    @property
    def metadata_service_version(self):
        tag = self._metadata_version
        if tag not in MD_SERVICE_VERSION:
            tag = 'master'
        return tag

    @property
    def ui_version(self):
        tag = self._ui_version 
        if tag not in UI_VERSIONS:
            tag ='master'
        return tag
        
        
    def _get_architecture_components(self):
        network = self._check_network()
        containers = [
            self._find_container(container) for container in 
            [
                self.database_container_name,
                self.metadata_service_container_name,
                self.ui_service_container_name,
                self.ui_container_name
            ]
        ]
        return network,containers
        
    def _resolve_ipaddr(self,container,network_name,wait_time=None):
        # Wait for 20 seconds until the IP addr of the 
        # database container is available
        wait_time = wait_time if wait_time is not None else self._max_ip_wait_time
        for i in range(wait_time):
            try:
                ipaddr = container.attrs['NetworkSettings']['Networks'][network_name]['IPAddress']
            except KeyError:
                ipaddr = ''

            if ipaddr == '':
                self._logger(f"Couldn't resolve IP Address for container {container.name} of image {container.image.tags}. Waiting for {wait_time-i} seconds",fg='red')
                container.reload()
            else:
                return ipaddr
            time.sleep(1)
        raise IpNotResolved(container_name=container.name,container_id=container.id)

    def _create_database(self):
        database_container = self._docker.containers.run(POSTGRES_IMAGE,\
                                            name=self.database_container_name,\
                                            detach=True,\
                                            ports=self._db_ports(),\
                                            environment=self._db_env_vars(),\
                                            network=self.network_name,)
        time.sleep(20)
        database_host = self._resolve_ipaddr(database_container,self.network_name,wait_time=120)
        return database_container, database_host

    def _db_env_vars(self):
        return dict(
            POSTGRES_USER=self._database_user,
            POSTGRES_PASSWORD=self._database_password ,
            POSTGRES_DB=self._database_name
        )

    def _mdservice_ports(self):
        return {
            f'8082/tcp':self._migration_port ,
            f'8080/tcp':self._metadata_port,
        }

    def _ui_ports(self):
        return {
            '3000/tcp':self._ui_port,
        }

    def _ui_service_ports(self):
        return {f"8083/tcp":self._ui_service_port}

    def _db_ports(self):
        return {
            f'{self._database_port}/tcp':self._database_port,
        }

    def _find_container(self,container_name):
        containers = self._docker.containers.list(filters={'name': container_name})
        if len(containers) ==0:
            return None
        return containers[0]
    
    def _create_network(self):
        network = self._docker.networks.create(self.network_name)
        time.sleep(5)
        return network

    def _check_network(self):
        try:
            return self._docker.networks.get(self.network_name)
        except NotFound as e:
            return None
        except:
            raise

    def _mdcontainer_env_vars(self,db_hostname):
        return dict(
            MF_METADATA_DB_HOST = db_hostname,
            MF_METADATA_DB_PORT = self._database_port,
            MF_METADATA_DB_USER = self._database_user,
            MF_METADATA_DB_PSWD = self._database_password,
            MF_METADATA_DB_NAME = self._database_name,
        )

    def _create_metadata_service(self,database_host):
        image = self._build_image(
            self._md_tempdir.name,
            os.path.join(self._md_tempdir.name,'Dockerfile'),
            self.metadata_service_container_name
        )
        return self._docker.containers.run(image.id,\
                                            name=self.metadata_service_container_name,
                                            detach=True,\
                                            stdin_open=True,\
                                            tty=True,\
                                            environment=self._mdcontainer_env_vars(database_host),\
                                            network=self.network_name,\
                                            ports=self._mdservice_ports(),\
                                        )


    def _create_ui_service(self,database_host):
        image = self._build_image(
            self._md_tempdir.name,
            os.path.join(self._md_tempdir.name,'Dockerfile.ui_service'),
            self.ui_service_container_name
        )
        aws_vars = {k:os.environ[k] for k in os.environ if 'AWS' in k}
        md_vars = self._mdcontainer_env_vars(database_host)
        md_vars.update(aws_vars)

        return self._docker.containers.run(image.id,\
                                            name=self.ui_service_container_name,
                                            detach=True,\
                                            stdin_open=True,\
                                            tty=True,\
                                            environment=md_vars,\
                                            network=self.network_name,\
                                            ports=self._ui_service_ports(),\
                                        )

    def _ui_env_vars(self,md_service_url):
        return {
            "METAFLOW_SERVICE":md_service_url
        }    

    def _create_ui(self,md_service_url):
        image = self._build_image(
            self._ui_tempdir.name,
            os.path.join(self._ui_tempdir.name,'Dockerfile'),
            self.ui_container_name
        )
        return self._docker.containers.run(image.id,\
                                        name=self.ui_container_name,
                                        detach=True,\
                                        stdin_open=True,\
                                        tty=True,\
                                        environment=self._ui_env_vars(md_service_url),\
                                        network=self.network_name,\
                                        ports=self._ui_ports(),\
                                        )


    def create(self):
        network, containers = self._get_architecture_components()
        if any(obj is not None for obj in containers+[network]):
            raise ExistingDeploymentException([container.name for container in containers+[network] if container is not None])
        # as everything is none, We can now deploy everything 
        network = self._create_network()
        self._logger(f"Created network :  {network.name}",fg='green')
        database_container, database_host = self._create_database()
        self._logger(f"Created Database container with host {database_host}",fg='green')
        self._clone_repo(MF_MD_REPO,self.metadata_service_version,self._md_tempdir.name)
        self._logger(f"Cloned Metadata Repo",fg='green')
        self._clone_repo(MF_UI_REPO,self.ui_version,self._ui_tempdir.name)
        self._logger(f"Cloned UI Repo",fg='green')
        md_service_container = self._create_metadata_service(database_host)
        self._logger(f"Running Metadata Service Container",fg='green')
        ui_service_container = self._create_ui_service(database_host)
        self._logger(f"Running UI Service Container",fg='green')
        ui_container = self._create_ui(f'http://localhost:{self._ui_service_port}')
        self._logger(f"Running UI Container",fg='green')
        md_service_url = f'http://localhost:{self._metadata_port}'
        self._logger(f"UI Is now deployed On http://localhost:{self._ui_port} with a Metadata service URL of {md_service_url}",fg='green')

    def _build_image(self,build_path,dockerfile,tag):
        image,log_generator = self._docker.images.build(path=build_path,\
                                                        dockerfile=dockerfile,\
                                                        tag=tag,)
        return image

    @staticmethod
    def _clone_repo(repo_url,version,dir,):
        from git import Repo
        cloned_repo = Repo.clone_from(repo_url, dir)
        cloned_repo.git.checkout(version)
    

    def teardown(self):
        network,containers = self._get_architecture_components()
        if all(obj is None for obj in containers+[network]):
            # raise No existing deployment exception
            self._logger(NO_DEPLOYMENT_FOUND,fg='red')
            return 

        for container in containers:
            if container is not None:
                self._logger(
                    f"Stopping Container {container.name}",fg='green'
                )
                self._teardown_container(container)
        if network is not None:
            time.sleep(10)
            self._logger(
                f"Removing network {network.name}",fg='green'
            )
            network.remove()
        self._logger(
            f"Finished Tearing Down Environment",fg='green'
        )
        
    
    @staticmethod
    def _teardown_container(container):
        container.stop(timeout=10)
        container.reload()
        container.remove()


    def check(self):
        network,containers = self._get_architecture_components()
        names = [container.name for container in containers+[network] if container is not None]
        if all(obj is None for obj in containers+[network]):
            # raise No existing deployment exception
            self._logger(
                NO_DEPLOYMENT_FOUND,fg='red'
            )
            return
        elif any(obj is None for obj in containers+[network]):
            # raise partial deployment exception
            self._logger(
                f"Found A Partial Deployment of Containers : \
                    {names}",fg='red'
            )
            return
        self._logger(
                f"All containers relevant to deployment found: \
                    {names}",fg='green'
            )
        