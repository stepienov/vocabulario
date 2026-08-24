import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

export default function PedagogyProductGap() {
  return (
    <Stack gap={28} style={{ maxWidth: 1100 }}>
      <Stack gap={8}>
        <H1>Vocabulario — luka pedagogiczna</H1>
        <Text tone="secondary">
          Macierz badań × produkt pod przyszłe US. Źródło prawdy:{" "}
          docs/analiza-pedagogiczna-produktowa.md. Stan kodu 2026-08-23. Książka
          Macaro/Graham/Woore: rozdz. 1 i 8 zasad (brak pełnego PDF).
        </Text>
        <Row gap={8} wrap>
          <Pill tone="success" active>
            FSRS + bogata karta = rdzeń
          </Pill>
          <Pill tone="warning" active>
            Luka = użycie, nie pamięć
          </Pill>
          <Pill tone="danger">Nie: XP, rankingi, Kahoot</Pill>
        </Row>
      </Stack>

      <Callout tone="success" title="Werdykt">
        Nie dokładać dopaminy. Domknąć pętlę: retrieval (jest) → input z
        constraintami (brak) → produkcja frazy/zdania (zalążek) → self-regulation
        (brak). Paywall na generację (historie, speak), nigdy na FSRS.
      </Callout>

      <Grid columns={4} gap={12}>
        <Stat value="jest" label="FSRS, karta v1, 3 tryby" tone="success" />
        <Stat value="P0" label="Adherence + weryfikator AI" tone="warning" />
        <Stat value="P1" label="Stories, chunks, SRL lite" />
        <Stat value="skip" label="Gest, XP, leaderboard" tone="danger" />
      </Grid>

      <H2>Mandat podwójny</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Rynek</CardHeader>
          <CardBody>
            <Text>
              Retencja D7/D30, jasna obietnica „słowo, którego używasz”,
              subskrypcja na koszt LLM. Packi dopiero po gate jakości (E-01
              parked).
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Uczciwa nauka</CardHeader>
          <CardBody>
            <Text>
              Feature zostaje, jeśli ma mechanizm z badań, mierzalny postęp inny
              niż kliknięcia, i nie zastępuje retrievalu nagrodą.
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <H2>Klasyfikacja źródeł</H2>
      <Table
        striped
        headers={["Waga", "Źródła", "Co wolno wnieść do US"]}
        rows={[
          [
            "Pedagogika",
            "Jorgensen; Kamzela SRS-Stories; Zhang; Hunutlu; Macaro 8 zasad",
            "Kolejka, historie i+1, SRL, skill > wiedza",
          ],
          [
            "NLP / ryzyko AI",
            "Mars; Naseem; Kotei; Chang & Bergen",
            "Mapa semantyczna, cache, weryfikator; nie „ucz się z BERT”",
          ],
          [
            "Łatwo nadinterpretować",
            "Nadarajan (Kahoot); tabela amō; Toumpaniari (4-latki)",
            "Wear-out gier; drill form (nie PDF); embodiment skip",
          ],
        ]}
        rowTone={["success", "info", "warning"]}
      />

      <H2>Macaro: 8 zasad vs apka</H2>
      <Text tone="secondary" size="small">
        Macaro, Graham, Woore 2015, rozdz. 1 / pdcinmfl.com. Zasada 8 spina
        wizję produktu.
      </Text>
      <Table
        striped
        stickyHeader
        headers={["#", "Zasada", "Vocabulario", "Luka"]}
        rows={[
          [
            "1",
            "Input L2 + negocjacja znaczenia",
            "Przykłady, TTS",
            "Brak „czego nie rozumiem”",
          ],
          [
            "2–3",
            "Mowa spontaniczna / jakość tury",
            "Brak",
            "Speak + zdanie, nie tylko gloss",
          ],
          [
            "4",
            "Chunking i strategie komunikacyjne",
            "Usages, peryfrazy na karcie",
            "Brak drillu frazy",
          ],
          [
            "5",
            "Czytanie/słuchanie + grafem–fonem",
            "IPA, TTS, CEFR examples",
            "Brak graded stories",
          ],
          [
            "6",
            "Self-efficacy: strategia → skutek",
            "Licznik due/new",
            "Brak celów i self-eval",
          ],
          [
            "7",
            "Pisanie ze znanego leksykonu",
            "Type-in lematu",
            "Nie ma kompozycji zdania",
          ],
          [
            "8",
            "Słownik/gramatyka służą skillom",
            "Silna wiedza leksykalna",
            "Pętla użycia niedomknięta",
          ],
        ]}
        rowTone={[
          "warning",
          "danger",
          "warning",
          "warning",
          "warning",
          "warning",
          "danger",
        ]}
      />

      <H2>Technika × status × priorytet US</H2>
      <Table
        striped
        stickyHeader
        headers={["Technika", "Status", "Siła", "US", "Anty-zabawka"]}
        rows={[
          ["FSRS / expanding spacing", "Jest", "Bardzo wysoka", "Utrzymać", "Nie paywallować"],
          [
            "Retrieval (8-choice, type-in)",
            "Jest",
            "Bardzo wysoka",
            "Utrzymać",
            "Nie spłycać do tap",
          ],
          ["Bogata karta v1", "Jest", "Wysoka", "Jakość P0", "Enrichment ≠ sesja"],
          [
            "Anti-lawina / catch-up",
            "Brak",
            "Wysoka (praktyka)",
            "P0",
            "Nie streak freeze",
          ],
          [
            "SRS-Stories i+1",
            "Brak",
            "Wysoka kierunkowo",
            "P1 paywall",
            "Mierzyć spotkania słowa",
          ],
          [
            "Weryfikator LLM",
            "Zalążek",
            "Wysoka (ryzyko)",
            "P0–P1",
            "Zaufanie > fluency AI",
          ],
          ["Cele + self-eval SRL", "Brak", "Wysoka adherence", "P1", "Due, nie XP"],
          [
            "Collocation / chunk drill",
            "Zalążek (usages)",
            "Wysoka",
            "P1 free",
            "Fraza w SRS",
          ],
          [
            "Drill koniugacji",
            "Tabela tak, rehearsal nie",
            "Wysoka (fleksja)",
            "P1",
            "Retrieval formy",
          ],
          ["Speak / pisanie zdania", "Brak", "Wysoka transfer", "P2 Pro", "Wąski ASR"],
          [
            "Mapa semantyczna",
            "Brak",
            "Średnia jako nauka",
            "P2",
            "CTA dodaj/retrieval",
          ],
          ["Packi startowe", "E-01 parked", "Biznes", "P3", "Nie wlewać w FSRS"],
          ["XP, ranking, Kahoot", "Brak", "Engagement ≠ nauka", "Nie robić", "Wear-out"],
          ["Embodiment / gest", "Brak", "Tylko preschool", "Skip", "Gimmick"],
        ]}
        rowTone={[
          "success",
          "success",
          "success",
          "warning",
          "info",
          "warning",
          "info",
          "info",
          "info",
          "neutral",
          "neutral",
          "neutral",
          "danger",
          "danger",
        ]}
      />

      <H2>Kolejność epików</H2>
      <Grid columns={4} gap={12}>
        <Card>
          <CardHeader trailing={<Pill tone="warning">P0</Pill>}>
            Higiena
          </CardHeader>
          <CardBody>
            <Text size="small">
              Catch-up cap, forecast skipu, onboarding SR, karta nie-ready nie
              wchodzi do sesji.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="info">P1</Pill>}>
            Różnica
          </CardHeader>
          <CardBody>
            <Text size="small">
              Historie na due, drill usages, drill czasów, SRL lite. Tu powstaje
              Pro.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill>P2</Pill>}>Skille</CardHeader>
          <CardBody>
            <Text size="small">
              Zdanie ze znanego leksykonu, speak na lemat, mapa z dodaj do Uczę
              się.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="neutral">P3</Pill>}>
            Wzrost
          </CardHeader>
          <CardBody>
            <Text size="small">
              Packi po DoR, iOS/web, teacher. Nie wcześniej niż stabilny COGS.
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="warning" title="Zależność twarda">
        Stories (P1) bez weryfikatora (P0) i bez anti-lawiny dają albo halucynację,
        albo tekst na 40 due, którego nikt nie przeczyta. Jorgensen: crowding
        zabija metodę.
      </Callout>

      <H2>Monetyzacja zgodna z badaniami</H2>
      <Table
        headers={["Warstwa", "Free", "Pro"]}
        rows={[
          ["Pamięć FSRS", "Pełna", "To samo — nie sprzedajemy powtórek"],
          ["Karta / enrichment", "Cap dzienny LLM", "Wyższy cap, priorytet kolejki"],
          ["Input", "0–1 historia / dzień", "SRS-Stories, dłuższe, audio"],
          ["Produkcja", "Type-in, chunk z karty", "Speak, zdania z verifierem"],
          ["Packi", "Własne listy + import", "Kuratorowane po E-01 DoR"],
        ]}
      />

      <Divider />
      <H3>Jednostka wartości w komunikacji</H3>
      <Text>
        Nie dni z rzędu. Słowa, które użytkownik spotkał w tekście, wyprodukował
        we frazie i nadal utrzymuje w FSRS.
      </Text>
    </Stack>
  );
}
