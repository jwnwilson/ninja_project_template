from ninja import Router

router = Router(
    tags=["{{project_slug|capitalize}}"],
)


@router.get("/additonal endpoint")
def get_{{project_slug}}(request):
    return {"message": "Hello, World!"}
