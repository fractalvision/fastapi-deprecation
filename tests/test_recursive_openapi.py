from fastapi import FastAPI
from fastapi_deprecation import deprecated, auto_deprecate_openapi


def test_recursive_openapi_deprecation():
    # 1. Create a sub-application
    sub_app = FastAPI()

    @sub_app.get("/sub-dep")
    @deprecated(deprecation_date="2025-01-01")
    def sub_endpoint():
        return {"msg": "sub"}

    # 2. Create root application and mount sub-app
    root_app = FastAPI()
    root_app.mount("/sub", sub_app)

    @root_app.get("/root-dep")
    @deprecated(deprecation_date="2025-01-01")
    def root_endpoint():
        return {"msg": "root"}

    # 3. Apply auto-deprecation (only on root app)
    auto_deprecate_openapi(root_app)

    # 4. Verify Root App OpenAPI
    root_openapi = root_app.openapi()
    paths = root_openapi["paths"]

    # Root endpoint should be deprecated
    assert paths["/root-dep"]["get"]["deprecated"] is True
    assert "Deprecated since" in paths["/root-dep"]["get"]["description"]

    # 5. Verify Sub App OpenAPI
    # Note: Mounted apps have their own OpenAPI schema.
    # auto_deprecate_openapi should modify sub_app routes too.

    # Get the sub-app's routes and check if they were modified
    # We can check by generating openapi for sub_app
    sub_openapi = sub_app.openapi()
    sub_paths = sub_openapi["paths"]

    # Sub endpoint should be deprecated
    assert "/sub-dep" in sub_paths
    assert (
        sub_paths["/sub-dep"]["get"].get("deprecated") is True
    ), "Sub-app endpoint was not marked deprecated"
    assert "Deprecated since" in sub_paths["/sub-dep"]["get"]["description"]
