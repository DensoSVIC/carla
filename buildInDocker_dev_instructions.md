# Steps to Build in docker container

## Run conatiner

- need to mount X11 / vulcan things so offscreen rendering / building works
- want to mount folders so save things on host after it runs
- namely the carla folder and the unreal engine fork that gets checked out should be mounted so have to reubild less 
```
docker run --name carla_10_build \
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
  -it ubuntu:22.04
```
- TODO remove this before putting on github: if use net host add orion to /etc/hosts
- do not need net host for build but do for running
- note UnrealEngine5_carla gets checkout by the ./CarlaSetup.sh script in carla so make sure it is mounted on same level as carla dir

## Prerequisite installs

- `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y sudo apt-utils dialog cmake tzdata libnss3 libxrandr2 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb-dev libxcomposite-dev libxcursor-dev libxdamage1 libxi6 libgbm-dev libpangocairo-1.0-0 libxss1 libasound2 libxkbcommon0`

## Gitlab user name / PAT
- need to link a github account and have permissions to epic uneral engine organization
- need to make a personal acess token (classic) with repo acess which will go in password field
- TODO doing this still prompted in the script but basic running script will be prompted for these
- `export GIT_LOCAL_CREDENTIALS=USER_NAME@PERSONAL_ACCESS_TOKEN`

## Build

- `export UE_ROOT=/root/UnrealEngine5_carla/`
- `cd /root/carla`
- `./CarlaSetup.sh`
- `cmake --build Build --target package`

### Speed Up Build

- above is slow mainly due to taring the binary content dirs
- if just want to build and include everything but do not need a tar.gz:
- in Unreal/CMakeLists.txt comment out the compression:
```
-    COMMAND ${CMAKE_COMMAND} -E echo "********** COMPRESSING PACKAGE STARTED **********"
-    COMMAND ${CMAKE_COMMAND}
-      -DCARLA_PACKAGE_PATH=${CARLA_PACKAGE_PATH}
-      -DCARLA_PACKAGE_ARCHIVE_PATH=${CARLA_PACKAGE_ARCHIVE_PATH}
-      -DCARLA_CURRENT_PACKAGE_PATH=${CARLA_CURRENT_PACKAGE_PATH}
-      -P${CMAKE_CURRENT_SOURCE_DIR}/Package/Compress.cmake
-    COMMAND ${CMAKE_COMMAND} -E echo "********** COMPRESSING PACKAGE COMPLETED **********"
+    # This part is slow
+    # COMMAND ${CMAKE_COMMAND} -E echo "********** COMPRESSING PACKAGE STARTED **********"
+    # COMMAND ${CMAKE_COMMAND}
+    #   -DCARLA_PACKAGE_PATH=${CARLA_PACKAGE_PATH}
+    #   -DCARLA_PACKAGE_ARCHIVE_PATH=${CARLA_PACKAGE_ARCHIVE_PATH}
+    #   -DCARLA_CURRENT_PACKAGE_PATH=${CARLA_CURRENT_PACKAGE_PATH}
+    #   -P${CMAKE_CURRENT_SOURCE_DIR}/Package/Compress.cmake
+    # COMMAND ${CMAKE_COMMAND} -E echo "********** COMPRESSING PACKAGE COMPLETED **********"
```



## Run

### Add New User

- Unreal without modification won't start as root
- I added in above run command just my group/user from to inside container then:
```
docker exec \
  --env=DISPLAY=$DISPLAY \
  --user=$(id -u):$(id -g) \
  --tty \
  --env=NVIDIA_VISIBLE_DEVICES=all \
  --env=NVIDIA_DRIVER_CAPABILITIES=all \
  -it carla_10_build /bin/bash
```
- + chmod the mounts

### Server

- `apt-get install freeglut3-dev mesa-utils`
- `./carla/Build/Package/Carla-0.10.0-Linux-Shipping/Linux/CarlaUnreal.sh`

### Client Python

- `python3 python3-pip`
- `python3 -m pip install ./Build/Package/Carla-0.10.0-Linux-Shipping/PythonAPI/carla/dist/carla-0.10.0-cp310-cp310-linux_x86_64.whl`
- `python3 yourPythonScriptWhichIncludesCarla.py`