"""
The purpose of this script is to create a localized metaflow deployment.
This script will expose 3 commands. 
- create 
- teardown
- check 
"""
from .deploy import DeployDockerMetalflow,ExistingDeploymentException
import click
from functools import partial
import datetime

TIME_FORMAT = "%Y-%m-%d %I:%M:%S %p"

def logger(base_logger,*args,**kwargs):
    msg = f'{datetime.datetime.now().strftime(TIME_FORMAT)} - UI Deployment Script - {args[0]}'
    base_logger(msg,**kwargs)

@click.group()
def deployment_cli():
    pass

@deployment_cli.command()
@click.option('--database-password',default="ByvI)Sr_uamaPx$w&Xp_LoB*DVBzTO+3oK{Z_Nw4SRcxut?-B>h]&WD}_mU!AgOm'\"")
@click.option('--database-name',default='metaflow')
@click.option('--database-user',default='metaflow')
@click.option('--database-port',default=5432)
@click.option('--md-version',default='2.1.0')
@click.option('--ui-version',default='v1.0.0')
def create(
    database_name='metaflow',
    database_password='password',
    database_user='metaflow',
    database_port = 5432,
    md_version=None,
    ui_version=None,
):
    #todo fix ports 
    echo = partial(logger,click.secho)
    echo(f'Creating A Metaflow Deployment With MD Version {md_version} and UI Version {ui_version}',fg='magenta')
    deployment = DeployDockerMetalflow(
        database_name = database_name,
        database_password = database_password,
        database_user = database_user,
        database_port = database_port,
        metadata_repo_version=md_version,
        ui_version=ui_version,
        logger=echo,
    )
    try:
        deployment.create()
    except ExistingDeploymentException as e:
        echo(
            f'{e.headline}\n{e.message}',fg='red'
        )

@deployment_cli.command()
def check():
    deployment = DeployDockerMetalflow(
        logger=partial(logger,click.secho),
    )
    deployment.check()

@deployment_cli.command()
def teardown():
    deployment = DeployDockerMetalflow(
        logger=partial(logger,click.secho),
    )
    deployment.teardown()

if __name__ == '__main__':
    deployment_cli()