from __future__ import annotations

import pathlib

EN = """
    <string name="correction_fix_card">Fix card</string>
    <string name="correction_report_title">Report a problem</string>
    <string name="correction_section_lemma">Lemma</string>
    <string name="correction_section_pos">Part of speech</string>
    <string name="correction_section_gloss">Primary gloss</string>
    <string name="correction_section_meanings">Meanings</string>
    <string name="correction_section_examples">Examples</string>
    <string name="correction_section_conjugation">Conjugation</string>
    <string name="correction_section_similar">Similar words</string>
    <string name="correction_section_pronunciation">Pronunciation</string>
    <string name="correction_section_other">Other</string>
    <string name="correction_note_label">Note</string>
    <string name="correction_note_hint">Describe what is wrong…</string>
    <string name="correction_validation">Select at least one section or write a note (min. 3 characters).</string>
    <string name="correction_submit">Submit report</string>
    <string name="correction_requires_online">Requires internet connection.</string>
    <string name="correction_result_accepted_title">Report accepted — card updated.</string>
    <string name="correction_result_rejected_title">Report not accepted.</string>
    <string name="correction_result_rejected_body">You can edit the card yourself — at your own risk. This creates your private copy.</string>
    <string name="correction_edit_self">Edit myself</string>
    <string name="correction_self_edit_title">Edit card</string>
    <string name="correction_field_lemma">Lemma</string>
    <string name="correction_field_pos">Part of speech</string>
    <string name="correction_field_gloss">Primary gloss</string>
    <string name="correction_field_extra_glosses">Extra glosses (one per line)</string>
    <string name="review_status_reported">Correction reported</string>
    <string name="review_status_accepted">Updated</string>
    <string name="review_status_rejected">Report rejected</string>
    <string name="review_status_user_edited">Edited manually</string>
    <string name="cd_voice_search">Voice search</string>
    <string name="voice_listening">Listening…</string>
    <string name="voice_listening_hint">Speak now</string>
    <string name="voice_tap_to_start">Tap Start to speak</string>
    <string name="voice_start">Start</string>
    <string name="voice_stop">Stop</string>
    <string name="voice_permission_denied">Microphone permission denied.</string>
    <string name="voice_unavailable">Speech recognition unavailable on this device.</string>
    <string name="settings_notifications">Notifications</string>
    <string name="settings_notifications_summary">Study reminders and card readiness</string>
    <string name="settings_notif_study">Study reminders</string>
    <string name="settings_notif_cards">Cards ready</string>
    <string name="settings_reminder_hour">Reminder hour (0–23)</string>
    <string name="notif_channel_study">Study</string>
    <string name="notif_channel_cards">Cards</string>
    <string name="notif_study_title">Time to review</string>
    <string name="notif_study_body">%1$d cards due</string>
    <string name="notif_cards_ready_title">Cards ready</string>
    <string name="notif_cards_ready_body">%1$d word(s) ready to study</string>
"""

PL = """
    <string name="correction_fix_card">Popraw kartę</string>
    <string name="correction_report_title">Zgłoś problem</string>
    <string name="correction_section_lemma">Lemat</string>
    <string name="correction_section_pos">Część mowy</string>
    <string name="correction_section_gloss">Główne tłumaczenie</string>
    <string name="correction_section_meanings">Znaczenia</string>
    <string name="correction_section_examples">Przykłady</string>
    <string name="correction_section_conjugation">Odmiana</string>
    <string name="correction_section_similar">Podobne słowa</string>
    <string name="correction_section_pronunciation">Wymowa</string>
    <string name="correction_section_other">Inne</string>
    <string name="correction_note_label">Notatka</string>
    <string name="correction_note_hint">Opisz błąd…</string>
    <string name="correction_validation">Wybierz co najmniej jedną sekcję lub wpisz notatkę (min. 3 znaki).</string>
    <string name="correction_submit">Wyślij zgłoszenie</string>
    <string name="correction_requires_online">Wymaga połączenia z internetem.</string>
    <string name="correction_result_accepted_title">Zgłoszenie uznane — kartę zaktualizowano.</string>
    <string name="correction_result_rejected_title">Zgłoszenie uznane za niezasadne.</string>
    <string name="correction_result_rejected_body">Możesz zedytować kartę samodzielnie — na własną odpowiedzialność. Powstanie Twoja prywatna kopia.</string>
    <string name="correction_edit_self">Edytuj samodzielnie</string>
    <string name="correction_self_edit_title">Edytuj kartę</string>
    <string name="correction_field_lemma">Lemat</string>
    <string name="correction_field_pos">Część mowy</string>
    <string name="correction_field_gloss">Główne tłumaczenie</string>
    <string name="correction_field_extra_glosses">Dodatkowe tłumaczenia (jedno w linii)</string>
    <string name="review_status_reported">Zgłoszono poprawkę</string>
    <string name="review_status_accepted">Poprawiono</string>
    <string name="review_status_rejected">Zgłoszenie odrzucone</string>
    <string name="review_status_user_edited">Edytowana ręcznie</string>
    <string name="cd_voice_search">Wyszukiwanie głosowe</string>
    <string name="voice_listening">Słucham…</string>
    <string name="voice_listening_hint">Mów teraz</string>
    <string name="voice_tap_to_start">Naciśnij Start, aby mówić</string>
    <string name="voice_start">Start</string>
    <string name="voice_stop">Stop</string>
    <string name="voice_permission_denied">Brak zgody na mikrofon.</string>
    <string name="voice_unavailable">Rozpoznawanie mowy niedostępne na tym urządzeniu.</string>
    <string name="settings_notifications">Powiadomienia</string>
    <string name="settings_notifications_summary">Przypomnienia o nauce i gotowość kart</string>
    <string name="settings_notif_study">Przypomnienia o nauce</string>
    <string name="settings_notif_cards">Karty gotowe</string>
    <string name="settings_reminder_hour">Godzina przypomnienia (0–23)</string>
    <string name="notif_channel_study">Nauka</string>
    <string name="notif_channel_cards">Karty</string>
    <string name="notif_study_title">Czas na powtórkę</string>
    <string name="notif_study_body">%1$d kart do powtórki</string>
    <string name="notif_cards_ready_title">Karty gotowe</string>
    <string name="notif_cards_ready_body">%1$d słów gotowych do nauki</string>
"""

root = pathlib.Path(__file__).resolve().parents[1] / "android/app/src/main/res"
for path in root.glob("values*/strings.xml"):
    block = PL if "values-pl" in path.as_posix() else EN
    text = path.read_text(encoding="utf-8")
    if "correction_fix_card" in text:
        continue
    path.write_text(text.replace("</resources>", block + "\n</resources>"), encoding="utf-8")
    print("updated", path.name)
