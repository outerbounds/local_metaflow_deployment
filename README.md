# Metaflow Local Deployment Tool 

This tool is meant to help deploy metaflow locally using docker. It will deploy a post-gres container, a metadata service , a UI service and a UI container. 


## Quick Setup 

1. Clone this repo. 
2. Install via `pip install .` or from github source 
3. As the UI requires AWS creds , please set AWS related configuations in the environment variables. 
4. Run the deployments
    1. Creating a local deployment 
    ```sh
    local-metaflow-deployment create 
    ```

    2. Checking preexisting deployment 
    ```sh
    local-metaflow-deployment check 
    ```

    2. Teardown a preexisting deployment 
    ```sh
    local-metaflow-deployment teardown 
    ```