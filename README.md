## Skrypt do Zarządzania Firmware ONU na OLT DASAN

Skrypt ułatwia zarządzanie firmware ONU (Optical Network Unit) na urządzeniach OLT (Optical Line Terminal) firmy DASAN. Umożliwia on wykonywanie następujących operacji:

* **Aktualizacja firmware:** Aktualizacja firmware dla określonych modeli ONU. Można wybrać konkretną wersję firmware lub zaktualizować wszystkie wersje.
* **Resetowanie ONU:** Resetowanie ONU, które zakończyły aktualizację firmware (status "Commit Complete").
* **Listowanie ONU do resetu:** Wyświetlanie listy ONU o statusie "Commit Complete", które są gotowe do resetu.
* **Listowanie wersji firmware:** Wyświetlanie listy wersji firmware dla określonego modelu ONU.
* **Listowanie dostępnych modeli:** Wyświetlanie listy unikalnych modeli ONU dostępnych na podanych portach OLT.

### Wymagania

* Python 3
* Biblioteka `netmiko` (można zainstalować za pomocą `pip install netmiko`)

### Użycie

Skrypt uruchamia się z linii poleceń, podając odpowiednie argumenty. Poniżej znajduje się opis dostępnych argumentów:

**Argumenty podstawowe:**

* `hostname`: Adres IP urządzenia OLT.
* `username`: Nazwa użytkownika do logowania na OLT.
* `password`: Hasło do logowania na OLT.
* `enable_password`: Hasło do trybu uprzywilejowanego (enable) na OLT.

**Argumenty operacji (wybierz jeden):**

* `--reset`: Resetuje ONU o statusie "Commit Complete".
* `--list-reset`: Wyświetla listę ONU o statusie "Commit Complete".
* `--firmware`: Wyświetla listę wersji firmware dla określonego modelu ONU (wymaga argumentu `--model`).
* `--upgrade <model> <firmware> <current_version> [exclude_version]`: Aktualizuje firmware dla określonego modelu ONU. 
    * `model`: Model ONU do aktualizacji.
    * `firmware`: Nazwa pliku firmware na serwerze FTP.
    * `current_version`: Aktualna wersja firmware(lub "all" dla wszystkich wersji). Można podać np. `3.0`, aby zaktualizować wszystkie wersje firmware zaczynające się od `3.0` (np. `3.0.1`, `3.0.15` itd.). 

    * `exclude_version` (opcjonalny): Wersja firmware, która ma zostać pominięta podczas aktualizacji.
* `--list-model`: Wyświetla listę unikalnych modeli ONU.

**Argumenty dodatkowe:**

* `--oltid`: ID portu(ów) OLT, oddzielone przecinkami (np. `1,2,3`).
* `--model`: Model ONU (wymagany dla `--firmware`).
* `--ftp-host`: Adres serwera FTP.
* `--ftp-user`: Nazwa użytkownika do logowania na serwer FTP.
* `--ftp-password`: Hasło do logowania na serwer FTP.

### Przykłady

**Resetowanie ONU na porcie OLT 1:**

```bash
python script.py <hostname> <username> <password> <enable_password> --reset --oltid 1
```

**Listowanie wersji firmware dla modelu HL-4GQVS2 na porcie OLT 2:**

```bash
python script.py <hostname> <username> <password> <enable_password> --firmware --oltid 2 --model HL-4GQVS2
```

**Aktualizacja firmware dla modelu HL-4GQVS2 na portach OLT 1 i 2, tylko dla ONU z wersją firmware zaczynającą się od "V3.0":**


```bash
python script.py <hostname> <username> <password> <enable_password> --upgrade HL-4GQVS2 G_ONU_HL-4GQVS2_V3-1-28p2_001-enc.bin V3.0 --oltid 1,2 --ftp-host <ftp_host> --ftp-user <ftp_user> --ftp-password <ftp_password>
```

### Uwagi

* Przed uruchomieniem skryptu upewnij się, że plik firmware znajduje się na serwerze FTP.
* Skrypt wymaga dostępu do OLT za pośrednictwem SSH.
* Upewnij się, że masz odpowiednie uprawnienia do wykonywania operacji na OLT.
* Autor nie ponosi odpowiedzialności za jakiekolwiek szkody wynikłe z użycia tego skryptu.
* Testowany na urządzeniach OLT: v5824G, V5816, V5812G.

### Podsumowanie

Ten skrypt stanowi  narzędzie do automatyzacji zarządzania firmware ONU na urządzeniach OLT DASAN. Pozwala to zaoszczędzić czas i zminimalizować ryzyko błędów podczas ręcznej konfiguracji. Pamiętaj, aby dostosować argumenty skryptu do swojej konfiguracji sieciowej.
