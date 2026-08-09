"""Modele Pydantic dla manifestów LSP."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenseItem(BaseModel):
    key: str
    label_l2: str
    person_grid: str | None = None


class PersonGrid(BaseModel):
    keys: list[str]
    labels: dict[str, str] = Field(default_factory=dict)


class VerbSpec(BaseModel):
    tenses: list[TenseItem] = Field(default_factory=list)
    non_finite: list[TenseItem] = Field(default_factory=list)
    person_grids: dict[str, PersonGrid] = Field(default_factory=dict)
    paradigm_rules: str = ""


class NounSpec(BaseModel):
    cases: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    genders: list[str] = Field(default_factory=list)


class AdjectiveSpec(BaseModel):
    full_declension: bool = False


class CardSection(BaseModel):
    key: str
    label_l2: str
    default_visible: bool = True


class LanguageManifest(BaseModel):
    code: str
    lsp_version: str
    name_en: str
    script: str = "Latn"
    rtl: bool = False
    inflection_kind: str = "person_tense"
    default_selected_tenses: list[str] = Field(default_factory=list)
    verbs: VerbSpec | None = None
    nouns: NounSpec | None = None
    adjectives: AdjectiveSpec | None = None
    ui_labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    card_sections: list[CardSection] = Field(default_factory=list)

    def tense_keys(self) -> list[str]:
        if not self.verbs:
            return []
        return [t.key for t in self.verbs.tenses]

    def non_finite_keys(self) -> list[str]:
        if not self.verbs:
            return []
        return [t.key for t in self.verbs.non_finite]

    def label_for_tense(self, tense_key: str, *, app_lang: str) -> str:
        ui = self.ui_labels.get(app_lang, {})
        if tense_key in ui:
            return ui[tense_key]
        for t in (self.verbs.tenses if self.verbs else []):
            if t.key == tense_key:
                return t.label_l2
        for t in (self.verbs.non_finite if self.verbs else []):
            if t.key == tense_key:
                return t.label_l2
        return tense_key.replace("_", " ")

    def as_language_pack_dict(self) -> dict:
        """Kształt zgodny z legacy GET /language-packs/{code}."""
        verbs = self.verbs
        tenses = verbs.tenses if verbs else []
        non_finite = verbs.non_finite if verbs else []
        return {
            "code": self.code,
            "name_en": self.name_en,
            "script": self.script,
            "rtl": self.rtl,
            "show_conjugation_default": bool(tenses),
            "conjugation_kind": self.inflection_kind,
            "tenses": [{"key": t.key, "label": t.label_l2} for t in tenses],
            "non_finite": [{"key": t.key, "label": t.label_l2} for t in non_finite],
            "default_selected_tenses": list(self.default_selected_tenses),
            "lsp_version": self.lsp_version,
        }
