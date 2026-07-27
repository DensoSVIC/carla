# Steps to Build in docker container

## Run conatiner

- need to mount X11 / vulcan things so offscreen rendering / building works
- want to mount folders so save things on host after it runs
- namely the carla folder and the unreal engine fork that gets checked out should be mounted so have to reubild less 
```
docker run --name carla_10_build \
  --privileged \
  --net=host \
  --gpus all \
  --env=DISPLAY=$DISPLAY \
  --env=NVIDIA_VISIBLE_DEVICES=all \
  --env=NVIDIA_DRIVER_CAPABILITIES=all \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v /usr/lib64/libvulkan.so.1:/usr/lib64/libvulkan.so.1 \
  -v /usr/lib64/libnvidia-gpucomp.so.595.58.03:/usr/lib64/libnvidia-gpucomp.so.595.58.03 \
  -v /usr/share/vulkan/icd.d:/usr/share/vulkan/icd.d \
  -v ./carla:/root/carla \
  -v ./UnrealEngine5_carla:/root/UnrealEngine5_carla \
  --rm \
  -it ubuntu:22.04
```
- TODO remove this before putting on github
- do not need net host for build but do for running
- if use net host add orion to /etc/hosts

## Prerequisite installs

- TODO check libfoonathan-memory-dev may not be necesacry with fixes to other build scripts
- `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y sudo apt-utils dialog cmake tzdata libnss3 libxrandr2 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb-dev libxcomposite-dev libxcursor-dev libxdamage1 libxi6 libgbm-dev libpangocairo-1.0-0 libxss1 libasound2 libxkbcommon0 libfoonathan-memory-dev`

## Gitlab user name / PAT
- need to link a github account and have permissions to epic uneral engine organization
- need to make a token with repo acess which will go in password field
- TODO doing this still prompted in the script
- `export GIT_LOCAL_CREDENTIALS=USER_NAME@PERSONAL_ACCESS_TOKEN`

## Build

- `export UE_ROOT=/root/UnrealEngine5_carla/`
- `cd /root/carla`
- `./CarlaSetup.sh`
- `cmake --build Build --target package`

## Run

- TODO check on rebuild if this is fixed
- `export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:./carla/Unreal/CarlaUnreal/Plugins/Carla/Binaries/Linux/`
- `apt-get install freeglut3-dev mesa-utils`