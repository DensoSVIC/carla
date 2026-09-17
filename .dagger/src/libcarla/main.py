from typing import Annotated

import dagger

from de_lib import DensoBase
from de_lib import credentials
from de_lib.models import Dependency

@dagger.object_type
class Libcarla(DensoBase):

    source: Annotated[
        dagger.Directory,
        dagger.Doc("Source directory to mount"),
        dagger.DefaultPath("/"),
    ]

    manifest_file: Annotated[
        dagger.File,
        dagger.Doc("Project manifest file (JSON)"),
        dagger.DefaultPath("/manifest.json"),
    ]

    @dagger.function
    async def store_jfrog_credentials(
        self,
        jfrog_token: Annotated[dagger.Secret, dagger.Doc("JFrog identity token")],
        jfrog_user: Annotated[dagger.Secret, dagger.Doc("JFrog username")],
    ) -> str:
        """Store JFrog credentials in a persistent cache volume for future calls.

        After storing, functions like dev-image, push-artifact, and
        fetch-artifact will use these credentials automatically when no
        explicit --jfrog-token / --jfrog-user is passed.
        """

        await credentials.store_many(
            {"jfrog-token": jfrog_token, "jfrog-user": jfrog_user}
        )
        keys = await credentials.list_keys()
        return f"JFrog credentials stored. Verified keys: {keys}"


    @dagger.function
    async def clear_jfrog_credentials(self) -> str:
        """Remove stored JFrog credentials from the cache volume."""

        await credentials.delete("jfrog-token")
        await credentials.delete("jfrog-user")
        return "JFrog credentials cleared from cache volume."


    @dagger.function
    async def list_credentials(self) -> str:
        """List all stored credential keys."""

        keys = await credentials.list_keys()
        return "\n".join(keys) if keys else "No credentials stored."


    @dagger.function
    async def base_image(
        self,
        jfrog_token: Annotated[dagger.Secret | None, dagger.Doc("JFrog identity token for fetching artifacts")] = None,
    ) -> dagger.Container:

        manifest = await self.manifest()

        container = self.build_dev_image(manifest, self.source, jfrog_token, {})
        container = (container
            .with_exec(["bash", "-c",
                r"""
                apt-get update
                apt-get install -y \
                    git \
                    git-lfs \
                    locales \
                    build-essential \
                    cmake \
                    python3 \
                    python3-dev \
                    python3-numpy \
                    fontconfig
                sed -i 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen
                locale-gen en_US.UTF-8
                update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
                echo 'git config --global http.postBuffer 524288000' > /etc/profile.d/99-gitbuf.sh
                """
            ])
            .with_env_variable("LANG", "en_US.UTF-8")
            .with_env_variable("LANGUAGE", "en_US:en")
            .with_env_variable("LC_ALL", "en_US.UTF-8")
        )

        return container

    @dagger.function
    async def artifacts(
        self,
        jfrog_token: Annotated[dagger.Secret | None, dagger.Doc("JFrog identity token for fetching artifacts")] = None,
    ) -> dagger.File:

        container = (await (await self.base_image(jfrog_token))
            .with_workdir("/app")
            .with_exec(["bash", "-c",
                f"""
                cmake -B build -DCMAKE_BUILD_TYPE=Release \
                    -DBUILD_CARLA_SERVER=OFF -DBUILD_CARLA_CLIENT=ON \
                    -DBUILD_EXAMPLES=OFF -DCMAKE_INSTALL_PREFIX=/tmp/usr/local
                cmake --build build -j$(nproc)
                cmake --install build
                """
            ])
            .with_exec(["bash","-c",
                """
                mkdir -p /tmp/usr/local/lib/pkgconfig
                cd build/_deps
                mv rpclib-src/include/rpc                               /tmp/usr/local/include/
                mv rpclib-build/librpc.a                                /tmp/usr/local/lib
                mv rpclib-build/rpclib.pc                               /tmp/usr/local/lib/pkgconfig/
                mkdir -p /tmp/usr/local/include/recastnavigation
                mv recastnavigation-src/Recast/Include/*                /tmp/usr/local/include/recastnavigation/
                mv recastnavigation-src/Detour/Include/*                /tmp/usr/local/include/recastnavigation/
                mv recastnavigation-src/DebugUtils/Include/*            /tmp/usr/local/include/recastnavigation/
                mv recastnavigation-src/DetourCrowd/Include/*           /tmp/usr/local/include/recastnavigation/
                mv recastnavigation-src/DetourTileCache/Include/*       /tmp/usr/local/include/recastnavigation/
                mv recastnavigation-build/recastnavigation.pc           /tmp/usr/local/lib/pkgconfig/
                mv recastnavigation-build/Recast/libRecast.a            /tmp/usr/local/lib/
                mv recastnavigation-build/Detour/libDetour.a            /tmp/usr/local/lib/
                mv recastnavigation-build/DetourCrowd/libDetourCrowd.a  /tmp/usr/local/lib/
                cd ../../ && rm -rf build
                cd /tmp && tar zcf libcarla.tar.gz usr/
                """
            ])
        )

        return container.file("/tmp/libcarla.tar.gz")

    @dagger.function
    async def upload_artifacts(
        self,
        jfrog_token: Annotated[dagger.Secret | None, dagger.Doc("JFrog identity token for fetching artifacts")] = None,
    ) -> str:
        LIBCARLA_VERSION = "latest"
        
        artifact_file = await self.artifacts(jfrog_token)
        manifest = await self.manifest()
        jfrog_token = await credentials.resolve("jfrog-token", jfrog_token)
        if not jfrog_token:
            raise RuntimeError("missing JFrog token. pass --jfrog-token, or run store-jfrog-credentials")
            
        container = self._base_container(manifest, manifest.dev_image, manifest.packages)
        container = container.with_file("/tmp/libcarla.tar.gz", artifact_file)
        container = self.setup_jfrog_cli(container, manifest.registry.artifacts, jfrog_token)

        return await self.jfrog_upload(container, path="/tmp/libcarla.tar.gz", name=f"libcarla/{LIBCARLA_VERSION}.tar.gz", repo=manifest.registry.artifacts_repo).stdout()
