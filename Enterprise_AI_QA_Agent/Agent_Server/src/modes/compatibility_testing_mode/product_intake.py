from __future__ import annotations

from typing import Any

from src.modes.compatibility_testing_mode.contracts import (
    AuthProfile,
    ProductArtifact,
    ProductAccessManifest,
    ProductEntrypoint,
    ProductNetworkProfile,
    ProductProfile,
    ProductTestScope,
    ProductType,
)


class CompatibilityProductIntake:
    def build_profile(self, arguments: dict[str, Any], context: Any) -> ProductProfile:
        explicit = arguments.get("product") if isinstance(arguments.get("product"), dict) else {}
        objective = str(arguments.get("objective") or getattr(context, "user_message", "") or "").strip()
        manifest = self.build_access_manifest(arguments, context)
        product_type = manifest.product_type
        entrypoint = self._primary_entrypoint(manifest)
        name = manifest.name

        artifacts = []
        if manifest.artifact and manifest.artifact.uri:
            artifacts.append(manifest.artifact)
        if entrypoint:
            artifacts.append(ProductArtifact(kind="entrypoint", uri=entrypoint))

        return ProductProfile(
            name=name,
            product_type=product_type,
            entrypoint=entrypoint,
            artifacts=artifacts,
            access_manifest=manifest,
            auth=manifest.auth,
            test_scope=manifest.test_scope.modules,
            priority_flows=manifest.test_scope.priority_flows,
            forbidden_actions=manifest.test_scope.forbidden_actions,
            data_policy=manifest.test_scope.data_policy,
            metadata={"objective": objective, "access_manifest_id": manifest.manifest_id} if objective else {"access_manifest_id": manifest.manifest_id},
        )

    def build_access_manifest(self, arguments: dict[str, Any], context: Any) -> ProductAccessManifest:
        explicit = arguments.get("product") if isinstance(arguments.get("product"), dict) else {}
        manifest_data = (
            arguments.get("product_access_manifest")
            or arguments.get("access_manifest")
            or explicit.get("access_manifest")
        )
        if isinstance(manifest_data, dict):
            try:
                return ProductAccessManifest.model_validate(manifest_data)
            except Exception:
                pass

        product_type = self._product_type(arguments, explicit)
        entrypoint = self._entrypoint(arguments, explicit)
        name = str(explicit.get("name") or arguments.get("product_name") or self._name_from_entrypoint(entrypoint) or "未命名产品").strip()
        artifact = self._artifact(arguments, explicit)
        auth_data = explicit.get("auth") if isinstance(explicit.get("auth"), dict) else {}
        network_data = explicit.get("network") if isinstance(explicit.get("network"), dict) else {}
        scope_data = explicit.get("test_scope") if isinstance(explicit.get("test_scope"), dict) else {}
        entrypoint_data = explicit.get("entrypoint") if isinstance(explicit.get("entrypoint"), dict) else {}

        auth = AuthProfile(
            strategy=str(arguments.get("auth_strategy") or auth_data.get("strategy") or "unspecified").strip() or "unspecified",
            username_ref=arguments.get("username_ref") or auth_data.get("username_ref"),
            password_ref=arguments.get("password_ref") or auth_data.get("password_ref"),
            token_ref=arguments.get("token_ref") or auth_data.get("token_ref"),
            manual_steps=self._string_list(arguments.get("manual_steps") or auth_data.get("manual_steps")),
        )
        return ProductAccessManifest(
            product_type=product_type,
            name=name,
            version=arguments.get("product_version") or explicit.get("version"),
            artifact=artifact,
            entrypoint=ProductEntrypoint(
                url=entrypoint if entrypoint.startswith(("http://", "https://")) else entrypoint_data.get("url"),
                package_name=arguments.get("package_name") or entrypoint_data.get("package_name"),
                activity=arguments.get("activity") or entrypoint_data.get("activity"),
                bundle_id=arguments.get("bundle_id") or entrypoint_data.get("bundle_id"),
                mini_program_path=arguments.get("mini_program_path") or entrypoint_data.get("mini_program_path"),
                command=arguments.get("command") or entrypoint_data.get("command"),
                metadata={key: value for key, value in entrypoint_data.items() if key not in {"url", "package_name", "activity", "bundle_id", "mini_program_path", "command"}},
            ),
            auth=auth,
            network=ProductNetworkProfile(
                requires_vpn=bool(arguments.get("requires_vpn") or network_data.get("requires_vpn") or False),
                base_api=arguments.get("base_api") or network_data.get("base_api"),
                proxy=arguments.get("proxy") or network_data.get("proxy"),
                metadata={key: value for key, value in network_data.items() if key not in {"requires_vpn", "base_api", "proxy"}},
            ),
            test_scope=ProductTestScope(
                modules=self._string_list(arguments.get("test_scope") or scope_data.get("modules") or explicit.get("test_scope")),
                priority_flows=self._string_list(arguments.get("priority_flows") or scope_data.get("priority_flows") or explicit.get("priority_flows")),
                exclude=self._string_list(arguments.get("exclude") or scope_data.get("exclude")),
                forbidden_actions=self._string_list(arguments.get("forbidden_actions") or scope_data.get("forbidden_actions") or explicit.get("forbidden_actions")),
                data_policy=str(arguments.get("data_policy") or scope_data.get("data_policy") or explicit.get("data_policy") or "unspecified").strip() or "unspecified",
            ),
            metadata={
                "source": "compatibility_product_intake",
                "objective": str(arguments.get("objective") or getattr(context, "user_message", "") or "").strip(),
            },
        )

    def _product_type(self, arguments: dict[str, Any], explicit: dict[str, Any]) -> ProductType:
        raw = str(arguments.get("product_type") or explicit.get("type") or explicit.get("product_type") or "").strip().lower()
        aliases = {
            "web/h5": "h5",
            "android": "android_app",
            "ios": "ios_app",
            "wechat": "wechat_mini_program",
            "weixin": "wechat_mini_program",
            "alipay": "alipay_mini_program",
            "linux": "linux_app",
        }
        normalized = aliases.get(raw, raw)
        if normalized in {"web", "h5", "android_app", "ios_app", "wechat_mini_program", "alipay_mini_program", "linux_app"}:
            return normalized  # type: ignore[return-value]

        entrypoint = self._entrypoint(arguments, explicit).lower()
        artifact_data = explicit.get("artifact") if isinstance(explicit.get("artifact"), dict) else {}
        artifact = str(
            artifact_data.get("uri")
            or (explicit.get("artifact") if not isinstance(explicit.get("artifact"), dict) else "")
            or arguments.get("artifact")
            or ""
        ).lower()
        if entrypoint.startswith(("http://", "https://")):
            return "web"
        if artifact.endswith((".apk", ".aab")):
            return "android_app"
        if artifact.endswith(".ipa"):
            return "ios_app"
        return "unknown"

    def _entrypoint(self, arguments: dict[str, Any], explicit: dict[str, Any]) -> str:
        entrypoint_data = explicit.get("entrypoint") if isinstance(explicit.get("entrypoint"), dict) else {}
        explicit_entrypoint = explicit.get("entrypoint") if not isinstance(explicit.get("entrypoint"), dict) else ""
        return str(
            arguments.get("target_url")
            or arguments.get("entrypoint")
            or entrypoint_data.get("url")
            or explicit_entrypoint
            or explicit.get("url")
            or ""
        ).strip()

    def _artifact(self, arguments: dict[str, Any], explicit: dict[str, Any]) -> ProductArtifact | None:
        artifact_data = explicit.get("artifact") if isinstance(explicit.get("artifact"), dict) else {}
        artifact_uri = str(
            arguments.get("artifact")
            or artifact_data.get("uri")
            or (explicit.get("artifact") if not isinstance(explicit.get("artifact"), dict) else "")
            or ""
        ).strip()
        if not artifact_uri:
            return None
        return ProductArtifact(
            kind=str(arguments.get("artifact_type") or artifact_data.get("kind") or "build_artifact").strip() or "build_artifact",
            uri=artifact_uri,
            metadata={key: value for key, value in artifact_data.items() if key not in {"kind", "uri"}},
        )

    def _primary_entrypoint(self, manifest: ProductAccessManifest) -> str:
        return (
            manifest.entrypoint.url
            or manifest.entrypoint.package_name
            or manifest.entrypoint.bundle_id
            or manifest.entrypoint.mini_program_path
            or manifest.entrypoint.command
            or (manifest.artifact.uri if manifest.artifact else "")
            or ""
        )

    def _name_from_entrypoint(self, entrypoint: str) -> str:
        if not entrypoint:
            return ""
        return entrypoint.replace("https://", "").replace("http://", "").split("/")[0]

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(value).strip()] if str(value).strip() else []
