import platform
import typing
import dagger
import dnsdv_pipeline_framework

@dagger.object_type
class Libcarla(dnsdv_pipeline_framework.DensoBase):

    source: typing.Annotated[
        dagger.Directory,
        dagger.Doc("Source directory to mount"),
        dagger.DefaultPath("."),
        dagger.Ignore(["**/.*"]), 
    ]

    manifest_file: typing.Annotated[
        dagger.File,
        dagger.Doc("Project manifest file (JSON)"),
        dagger.DefaultPath("manifest.json"),
    ]

    @dagger.function
    async def store_jfrog_credentials(
        self,
        jfrog_token: typing.Annotated[dagger.Secret, dagger.Doc("JFrog identity token")],
        jfrog_user: typing.Annotated[dagger.Secret, dagger.Doc("JFrog username")],
    ) -> str:
        """Store JFrog credentials in a persistent cache volume for future calls.

        After storing, functions like dev-image, push-artifact, and
        fetch-artifact will use these credentials automatically when no
        explicit --jfrog-token / --jfrog-user is passed.
        """

        await dnsdv_pipeline_framework.credentials.store_many(
            {"jfrog-token": jfrog_token, "jfrog-user": jfrog_user}
        )
        keys = await dnsdv_pipeline_framework.credentials.list_keys()
        return f"JFrog credentials stored. Verified keys: {keys}"

    @dagger.function
    async def clear_jfrog_credentials(self) -> str:
        """Remove stored JFrog credentials from the cache volume."""

        await dnsdv_pipeline_framework.credentials.delete("jfrog-token")
        await dnsdv_pipeline_framework.credentials.delete("jfrog-user")
        return "JFrog credentials cleared from cache volume."

    @dagger.function
    async def list_credentials(self) -> str:
        """List all stored credential keys."""

        keys = await dnsdv_pipeline_framework.credentials.list_keys()
        return "\n".join(keys) if keys else "No credentials stored."

    @dagger.function
    async def artifacts(
        self,
        jfrog_token: typing.Annotated[dagger.Secret | None, dagger.Doc("JFrog identity token for fetching artifacts")] = None,
        target_self: typing.Annotated[bool, dagger.Doc("Override architecture.target to build artifacts for current system architecture")] = False,
    ) -> dagger.Container:

        manifest = await self.manifest()
        
        if manifest.architecture.target != platform.uname().machine and not target_self:
            raise Exception(f"{manifest.name} artifacts for target {manifest.architecture.target} cannot be compiled on this system")

        jfrog_token = await dnsdv_pipeline_framework.credentials.resolve("jfrog-token", jfrog_token)

        container = self.build_dev_image(manifest, self.source, jfrog_token, {})
        container = (container
            .with_exec(["bash", "-c",
                r"""
                set -e
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

        container = (container
            .with_exec(["bash", "-c",
                f"""
                set -e
                cmake -B build -DCMAKE_BUILD_TYPE=Release \
                    -DBUILD_CARLA_SERVER=OFF -DBUILD_CARLA_CLIENT=ON \
                    -DBUILD_EXAMPLES=OFF -DCMAKE_INSTALL_PREFIX=/tmp/usr/local
                cmake --build build -j$(nproc)
                cmake --install build
                """
            ])
            .with_exec(["bash","-c",
                f"""
                set -e
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
                cd /tmp && tar zcf {manifest.name}.{manifest.version}.{platform.uname().machine}.tar.gz usr/
                """
            ])
        )

        return container.file(f"/tmp/{manifest.name}.{manifest.version}.{platform.uname().machine}.tar.gz")

    @dagger.function
    async def upload_artifacts(
        self,
        jfrog_token: typing.Annotated[dagger.Secret | None, dagger.Doc("JFrog identity token for fetching artifacts")] = None,
        target_self: typing.Annotated[bool, dagger.Doc("Override architecture.target to build artifacts for current system architecture")] = False,
    ) -> str:

        manifest = await self.manifest()

        if manifest.architecture.target != platform.uname().machine and not target_self:
            raise Exception(f"{manifest.name} artifacts for target {manifest.architecture.target} cannot be compiled on this system")

        artifacts = await self.artifacts(jfrog_token, target_self)

        jfrog_token = await dnsdv_pipeline_framework.credentials.resolve("jfrog-token", jfrog_token)
        if jfrog_token is None:
            raise RuntimeError(
                "No JFrog token provided and none found in cache. "
                "Pass --jfrog-token or run store-jfrog-credentials first."
            )

        container = self.build_dev_image(manifest, self.source, jfrog_token, {})
        container = container.with_file("/tmp/libcarla.tar.gz", artifacts)

        return await self.jfrog_upload(
            container, path="/tmp/libcarla.tar.gz",
            name=f"{manifest.name}/{manifest.name}.{manifest.version}.{platform.uname().machine}.tar.gz",
            repo=manifest.registry.artifacts_repo.strip("/")
        ).stdout()
