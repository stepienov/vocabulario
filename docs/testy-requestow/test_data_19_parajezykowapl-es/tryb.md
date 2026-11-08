# Tryb testów

Testuje się jedną parę naraz. Najpierw polski i hiszpański.

Pętla dla pary:

1. Usunąć zapis cache haseł tej pary.
2. Puścić cały zestaw przez wyszukiwanie, które idzie do modelu tak jak aplikacja.
3. Z wyniku wyciągnąć, czego brakuje i co jest fałszywe. Ustalić przyczynę w odpowiedzi modelu albo w kodzie, który wynik przycina.
4. Poprawić przyczynę.
5. Usunąć cache i puścić zestaw od nowa.
6. Do następnej pary przejść tylko wtedy, gdy zestaw tej pary przechodzi w całości.
7. Jeśli przy późniejszej parze zmieni się pytanie do modelu, testy wracają do pierwszej pary i idą od nowa.

W tym przebiegu jest tylko pierwsza para.
