from django.contrib.admindocs.utils import (
    replace_named_groups,
    replace_unnamed_groups,
)
from drf_spectacular.generators import *
from rest_framework.schemas.generators import _PATH_PARAMETER_COMPONENT_RE


def simplify_regex(pattern):
    r"""
    Clean up urlpattern regexes into something more readable by humans. For
    example, turn "^(?P<sport_slug>\w+)/athletes/(?P<athlete_slug>\w+)/$"
    into "/<sport_slug>/athletes/<athlete_slug>/".
    """
    pattern = replace_named_groups(pattern)
    pattern = replace_unnamed_groups(pattern)
    # clean up any outstanding regex-y characters.
    # change original replace method
    # replace ^ and ?
    # replace /$ or $/ to /
    # replace \$ to $ # this means we have $ in the url
    pattern = re.sub(r"(/\$) |(\$/)", "/", pattern.replace("^", "").rstrip("$").replace("?", "")).replace(r"\$", "$")
    if not pattern.startswith("/"):
        pattern = "/" + pattern
    return pattern


class EndpointEnumerator(EndpointEnumerator):
    def get_path_from_regex(self, path_regex):
        path = simplify_regex(path_regex)

        # Strip Django 2.0 convertors as they are incompatible with uritemplate format
        path = re.sub(_PATH_PARAMETER_COMPONENT_RE, r"{\g<parameter>}", path)
        # bugfix oversight in DRF regex stripping
        path = path.replace("\\.", ".")
        return path


class SchemaGenerator(SchemaGenerator):
    endpoint_inspector_cls = EndpointEnumerator

    def _initialise_endpoints(self):
        """filter pattern with api version to ignore the unrelated api"""
        if self.endpoints is None:
            self.inspector = self.endpoint_inspector_cls(self.patterns, self.urlconf)
            patterns = None
            if self.api_version:
                patterns = self.filter_pattern_with_api_version()
            self.endpoints = self.inspector.get_api_endpoints(patterns)

    def filter_pattern_with_api_version(self):
        patterns = []
        for pattern in self.inspector.patterns:
            if pattern.namespace == self.api_version:
                patterns.append(pattern)
        return patterns

    def parse_view_tag(self, input_request, public, schema_url_name="schema"):
        tags_set = set()
        self._initialise_endpoints()
        endpoints = self._get_paths_and_endpoints()
        if spectacular_settings.SCHEMA_PATH_PREFIX is None:
            # estimate common path prefix if none was given. only use it if we encountered more
            # than one view to prevent emission of erroneous and unnecessary fallback names.
            non_trivial_prefix = len(set([view.__class__ for _, _, _, view in endpoints])) > 1
            if non_trivial_prefix:
                path_prefix = os.path.commonpath([path for path, _, _, _ in endpoints])
                path_prefix = re.escape(path_prefix)  # guard for RE special chars in path
            else:
                path_prefix = "/"
        else:
            path_prefix = spectacular_settings.SCHEMA_PATH_PREFIX
        if not path_prefix.startswith("^"):
            path_prefix = "^" + path_prefix  # make sure regex only matches from the start

        for path, path_regex, method, view in endpoints:
            # ignore the path
            view.schema.path_prefix = path_prefix
            view.schema.path = path
            tags = view.schema.get_tags()
            if tags and schema_url_name not in view.schema._tokenize_path():
                tags_set.add(*tags)
        return tags_set

    def parse(self, input_request, public, page: str = None, page_all_tag: str = "All", module_mapping: dict = None):
        """Iterate endpoints generating per method path operations."""
        # check page settings
        if module_mapping is None:
            page_mapping_check = False
            module_name = " "
        else:
            page_mapping_check = page in module_mapping
            if page_mapping_check:
                module_name = module_mapping[page]
            else:
                module_name = ""
        page_setting_check = page and page != page_all_tag

        result = {}
        self._initialise_endpoints()
        endpoints = self._get_paths_and_endpoints()

        if spectacular_settings.SCHEMA_PATH_PREFIX is None:
            # estimate common path prefix if none was given. only use it if we encountered more
            # than one view to prevent emission of erroneous and unnecessary fallback names.
            non_trivial_prefix = len(set([view.__class__ for _, _, _, view in endpoints])) > 1
            if non_trivial_prefix:
                path_prefix = os.path.commonpath([path for path, _, _, _ in endpoints])
                path_prefix = re.escape(path_prefix)  # guard for RE special chars in path
            else:
                path_prefix = "/"
        else:
            path_prefix = spectacular_settings.SCHEMA_PATH_PREFIX
        if not path_prefix.startswith("^"):
            path_prefix = "^" + path_prefix  # make sure regex only matches from the start

        for path, path_regex, method, view in endpoints:
            # ignore the path
            try:
                view.schema.path_prefix = path_prefix
                view.schema.path = path
                tags = view.schema.get_tags()
                if page_setting_check:
                    if page_mapping_check:
                        if module_name not in view.__class__.__module__:
                            continue
                    elif not (tags and page in tags):
                        continue
            except Exception:
                tags = None

            view.request = spectacular_settings.GET_MOCK_REQUEST(method, path, view, input_request)

            if not (public or self.has_view_permissions(path, method, view)):
                continue

            if view.versioning_class and not is_versioning_supported(view.versioning_class):
                warn(
                    f'using unsupported versioning class "{view.versioning_class}". view will be '
                    f"processed as unversioned view."
                )
            elif view.versioning_class:
                version = (
                    self.api_version  # explicit version from CLI, SpecView or SpecView request
                    or view.versioning_class.default_version  # fallback
                )
                if not version:
                    continue
                path = modify_for_versioning(self.inspector.patterns, method, path, view, version)
                if not operation_matches_version(view, version):
                    continue

            assert isinstance(view.schema, AutoSchema), (
                f"Incompatible AutoSchema used on View {view.__class__}. Is DRF's "
                f'DEFAULT_SCHEMA_CLASS pointing to "drf_spectacular.openapi.AutoSchema" '
                f"or any other drf-spectacular compatible AutoSchema?"
            )
            with add_trace_message(getattr(view, "__class__", view)):
                operation = view.schema.get_operation(path, path_regex, path_prefix, method, self.registry)

            # handle some times we will not get tags before the last check
            if tags is None:
                tags = operation.get("tags")
                if page_setting_check:
                    if page_mapping_check:
                        # this is check by previous
                        pass
                    elif not (tags and page in tags):
                        continue

            # operation was manually removed via @extend_schema
            if not operation:
                continue

            if spectacular_settings.SCHEMA_PATH_PREFIX_TRIM:
                path = re.sub(pattern=path_prefix, repl="", string=path, flags=re.IGNORECASE)

            if spectacular_settings.SCHEMA_PATH_PREFIX_INSERT:
                path = spectacular_settings.SCHEMA_PATH_PREFIX_INSERT + path

            if not path.startswith("/"):
                path = "/" + path

            if spectacular_settings.CAMELIZE_NAMES:
                path, operation = camelize_operation(path, operation)

            result.setdefault(path, {})
            result[path][method.lower()] = operation

        return result

    def get_schema(self, request=None, public=False, page=None, page_all_tag=None, module_mapping=None):
        """Generate a OpenAPI schema."""
        reset_generator_stats()
        result = build_root_object(
            paths=self.parse(request, public, page, page_all_tag, module_mapping),
            components=self.registry.build(spectacular_settings.APPEND_COMPONENTS),
            version=self.api_version or getattr(request, "version", None),
        )
        for hook in spectacular_settings.POSTPROCESSING_HOOKS:
            result = hook(result=result, generator=self, request=request, public=public)

        return sanitize_result_object(normalize_result_object(result))
