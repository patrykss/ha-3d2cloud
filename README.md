# HA 3d2cloud

Dodatek Home Assistant do odbierania timelapsów z drukarek 3D (Moonraker/Klipper), kolejkowania i opcjonalnego uploadu do YouTube.

- **Nazwa:** HA 3d2cloud
- **Maintainer:** patrykss
- **Repozytorium:** https://github.com/patrykss/ha-3d2cloud
- **Obraz bazowy:** `python:3.11-alpine`
- **Panel:** Ingress, port 8080, ikona `mdi:cloud-check-variant`

## Struktura

```text
ha-3d2cloud/
├── config.yaml
├── Dockerfile
├── requirements.txt
├── README.md
├── rootfs/
│   └── main.py
└── scripts/
    └── upload_timelapse.sh
```

Nie ma `build.yaml` ani s6-overlay. `config.yaml` jest manifestem dodatku wymaganym przez Home Assistant.

## Instalacja

1. Umieść katalog dodatku w repozytorium dodatków, np. w repozytorium GitHub `patrykss/ha-3d2cloud`.
2. W Home Assistant przejdź do **Ustawienia → Dodatki → Sklep z dodatkami → ⋮ → Repozytoria** i dodaj:
   `https://github.com/patrykss/ha-3d2cloud`
3. Zainstaluj **HA 3d2cloud**, ustaw opcje i uruchom dodatek.
4. Panel otworzysz z poziomu Home Assistant przez Ingress.

Dodatek udostępnia także port hosta `8080/tcp`, aby drukarka w LAN mogła przesyłać pliki bez przechodzenia przez Ingress. Jeśli port 8080 jest zajęty na hoście, zmień mapowanie `8080/tcp` w `config.yaml` (np. na `8088`) i odpowiednio zmień URL w skrypcie drukarki.

## Opcje dodatku

| Opcja | Znaczenie |
|---|---|
| `api_token` | Opcjonalny sekret wymagany w nagłówku `X-API-Token`. Zalecany w sieci LAN. |
| `printer_name` | Nazwa drukarki w tytule filmu. |
| `title_template` | Szablon tytułu, domyślnie `{printer} - {filename} {date}`. |
| `youtube_enabled` | Włącza lub pomija wysyłkę na YouTube. |
| `youtube_access_token` | Krótkotrwały token OAuth (może być odświeżany poniższymi danymi). |
| `youtube_refresh_token` | Refresh token OAuth Google. |
| `youtube_client_id` / `youtube_client_secret` | Dane klienta OAuth. |
| `youtube_privacy_status` | `private`, `unlisted` lub `public`. |
| `youtube_category_id` | Kategoria YouTube, domyślnie `22`. |
| `max_upload_mb` | Maksymalny rozmiar pliku; domyślnie 4096 MB. |

### YouTube OAuth

Aby wysyłać filmy, skonfiguruj projekt w Google Cloud, włącz YouTube Data API v3 i uzyskaj dane OAuth z uprawnieniem `youtube.upload`. Wprowadź refresh token, client ID i client secret. Ustaw `youtube_enabled: true`.

Jeżeli `youtube_enabled` jest wyłączone, worker pomija wysyłkę i usuwa plik po obsłużeniu kolejki. Jeżeli wysyłka się nie powiedzie, plik jest przenoszony do `/data/failed` i nie jest automatycznie kasowany — pozwala to uniknąć utraty materiału. Po poprawnym uploadzie plik z `/data/processing` jest usuwany.

## API

`POST http://IP_HA:8080/api/upload`

Żądanie `multipart/form-data`, pole pliku: `file`.

Przykład:

```bash
curl --fail --show-error \
  -H "X-API-Token: TWOJ_SEKRET" \
  -F "file=@/path/to/timelapse.mp4" \
  http://IP_HA:8080/api/upload
```

Odpowiedź przyjęcia do kolejki: HTTP `202` i JSON zawierający `accepted: true`. To potwierdza zapis pliku do kolejki, nie zakończenie wysyłki na YouTube.

Pozostałe endpointy:
- `GET /api/status` — liczba plików w kolejce, w trakcie i w katalogu błędów.
- `GET /health` — test działania.

## Moonraker / Klipper

Skopiuj `scripts/upload_timelapse.sh` na hosta drukarki, np. do `/home/pi/printer_data/scripts/`, i nadaj uprawnienia:

```bash
chmod +x /home/pi/printer_data/scripts/upload_timelapse.sh
```

Ustaw zmienne środowiskowe (np. w pliku konfiguracyjnym usługi/skryptu):

```bash
export HA_3D2CLOUD_URL="http://192.168.1.10:8080"
export HA_3D2CLOUD_TOKEN="TWOJ_SEKRET"
```

Wywołaj skrypt z pełną ścieżką do gotowego pliku:

```bash
/home/pi/printer_data/scripts/upload_timelapse.sh "/home/pi/timelapse/print.mp4"
```

### Podpięcie do Moonraker Timelapse

Oficjalny komponent `moonraker-timelapse` udostępnia generowanie filmu oraz endpoint renderowania, ale jego standardowa konfiguracja nie definiuje uniwersalnego pola uruchamiania dowolnego skryptu po renderze. Dlatego skrypt jest przygotowany jako post-upload hook: należy wywołać go z mechanizmu post-processingu dostępnego w używanej instalacji lub z własnego wrappera uruchamianego po zakończeniu renderowania.

Nie podpinaj go do `TIMELAPSE_RENDER` przed zakończeniem renderowania — plik musi być kompletny i zamknięty przez FFmpeg. Skrypt usuwa lokalny plik wyłącznie po potwierdzeniu HTTP 202 i `accepted: true`. Przy błędzie sieci, błędnej autoryzacji lub błędzie API plik lokalny pozostaje na drukarce.

## Bezpieczeństwo i utrzymanie

- Ustaw `api_token`; bez niego każdy host, który może dotrzeć do portu 8080, może wysłać plik.
- Ogranicz port 8080 regułami firewalla do sieci drukarki/LAN. Nie wystawiaj go bezpośrednio do Internetu.
- Włącz TLS przez zaufany reverse proxy, jeśli przesyłasz przez niezaufaną sieć.
- Kolejka, pliki w trakcie i pliki błędne są przechowywane w `/data`.
- Pliki są zapisywane najpierw pod tymczasową nazwą `.part`, a następnie atomowo przenoszone do kolejki.
- Dozwolone rozszerzenia: `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`.
- Nieudane uploady YouTube są zachowywane w `/data/failed`; usuń je ręcznie po sprawdzeniu lub ponów przetwarzanie.
- Dla dużych plików zaplanuj odpowiednią ilość miejsca w katalogu danych Home Assistanta.

## Licencja

MIT
