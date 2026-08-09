"""Public meta endpoints — LSP language packs / tense catalogs."""



from fastapi import APIRouter, HTTPException



from app.lsp import available_codes, get_manifest, has_manifest

from app.lsp.constants import SUPPORTED_L2_LANGS



router = APIRouter(tags=["meta"])





@router.get("/lsp")

async def list_lsp():

    """Manifesty LSP — zaimplementowane języki nauki."""

    codes = sorted(SUPPORTED_L2_LANGS)

    implemented = set(available_codes())

    return {

        "supported": codes,

        "implemented": sorted(implemented),

        "pending": sorted(c for c in codes if c not in implemented),

    }





@router.get("/lsp/{code}")

async def get_lsp_manifest(code: str):

    key = code.strip().lower()

    if not has_manifest(key):

        raise HTTPException(status_code=404, detail=f"LSP not implemented: {code}")

    m = get_manifest(key)

    return m.model_dump()





@router.get("/language-packs")

async def list_language_packs():

    packs = []

    for code in sorted(SUPPORTED_L2_LANGS):

        if not has_manifest(code):

            raise HTTPException(

                status_code=503,

                detail=f"LSP manifest missing for {code}",

            )

        packs.append(get_manifest(code).as_language_pack_dict())

    return {"packs": packs}





@router.get("/language-packs/{code}")

async def get_pack(code: str):

    key = code.strip().lower()

    if key not in SUPPORTED_L2_LANGS:

        raise HTTPException(status_code=404, detail=f"Unknown language: {code}")

    if not has_manifest(key):

        raise HTTPException(status_code=404, detail=f"LSP not implemented: {code}")

    return get_manifest(key).as_language_pack_dict()

