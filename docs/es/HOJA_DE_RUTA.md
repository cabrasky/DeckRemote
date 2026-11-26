# Hoja de ruta: de "proyecto friki" a "4 clics"

[🇬🇧 English version](../ROADMAP.md)

El objetivo: alguien piensa *"quiero usar la Steam Deck como mando"* y en un par de clics lo tiene funcionando. Sin Konsole, sin IPs y sin contraseñas.

## Qué estorba hoy

| Obstáculo | Por qué molesta |
|---|---|
| Modo Escritorio + Konsole | La mayoría de usuarios de Deck nunca ha abierto una terminal |
| Contraseña de `sudo` | Muchos nunca la han puesto |
| Instalar usbip-win2 en el PC | Programa técnico, en inglés y que instala un driver |
| Escribir la IP y elegir `usbip-vudc.0` | Nadie sabe qué es eso |
| Hacer *Attach* cada vez | Un rollo en cada partida |
| Mando HID genérico, no de Xbox | Muchos juegos de PC solo aceptan XInput |

## Propuestas, de más a menos impacto

### 1. Emular un mando de Xbox 360, para que funcione en todos los juegos
El kernel de la Deck trae **FunctionFS** (`CONFIG_USB_CONFIGFS_F_FS=y`). Con él, el dispositivo virtual puede presentarse como **Xbox 360 Controller** (`045e:028e`) con sus descriptores propios. Windows lo reconoce con su driver de serie, como **XInput**, igual que un mando de Xbox con cable. Es la mayor mejora de compatibilidad: todos los juegos de PC, sin programas extra. Además, con XInput llega la **vibración** de vuelta, que podría mover la háptica de la Deck.

### 2. App compañera para Windows: adiós a IPs y a `usbip-vudc.0`
Un único instalador (`DeckRemote-Setup.exe`, o un paquete de **winget** / Microsoft Store) que:
- instala usbip-win2 por debajo (o incluye su driver);
- abre una ventana sencilla que **encuentra la Deck sola** y muestra un botón grande de **Conectar**.

Descubrimiento automático: mientras la app está abierta, la Deck se anuncia como `_deckremote._tcp` por **mDNS/Bonjour** (SteamOS ya trae Avahi). La app del PC la encuentra y conecta sola. Se mantiene la idea de "nada de fondo": la app del PC solo funciona mientras está abierta.

### 3. Plugin de Decky Loader: adiós a Konsole y a sudo
[Decky Loader](https://decky.xyz) es la tienda de plugins más usada en la Deck, y el backend de sus plugins **ya corre como root**. Así que:
- Instalación: Decky → Tienda → *DeckRemote* → Instalar. Son 2–3 clics, desde el Modo Juego.
- Sin contraseña ni regla de sudo: el plugin hace lo mismo que `gadget.sh`.
- Un panel en el menú rápido (⋯) con un interruptor **"Usar como mando del PC"**, el estado y la IP del PC.
- El plugin crea el acceso *DeckRemote* en Steam (la parte que lee el mando) con su arte.

### 4. Emparejamiento y seguridad
USB/IP no tiene autenticación. Para un público general:
- un **código de emparejamiento** de 4 cifras en la Deck que confirmas en el PC (la app compañera lo comprueba antes de conectar);
- o una regla de cortafuegos, solo mientras la app está abierta, que deje llegar al puerto 3240 únicamente al PC emparejado.

### 5. Pulido
- **Plantilla de Steam Input** ya hecha (palancas traseras asignadas, giroscopio como stick derecho al mantener un gatillo).
- Selector de modo: *Mando genérico* / *Mando de Xbox*.
- Medidor de latencia y aviso de Wi‑Fi flojo.
- Más idiomas: los textos están en una sola tabla en `deckremote.py`.

### 6. Distribución
| Canal | Para quién | Esfuerzo |
|---|---|---|
| **GitHub Releases**: un ZIP con instalador `.desktop` de doble clic | Gente que trastea | Bajo |
| **Tienda de Decky Loader** | La mayoría de usuarios "avanzados" de Deck | Medio |
| **winget / Microsoft Store** (app compañera) | Cualquier usuario de Windows | Medio |
| **Flatpak en Discover** | No vale por sí solo: un Flatpak no puede crear dispositivos USB virtuales (necesita root y configfs) | — |

## Cómo quedaría

1. **Deck:** Decky → Tienda → *DeckRemote* → Instalar.
2. **PC:** instalar *DeckRemote* desde winget o la Microsoft Store.
3. **A jugar:** en la Deck, ⋯ → *DeckRemote* → activar. En el PC, abrir *DeckRemote* → "Steam Deck encontrada" → **Conectar**.

Unos 4 clics por equipo la primera vez, y 2 en cada partida. Sin terminal, sin IPs y sin contraseñas.

## Orden recomendado
1. Emulación de Xbox 360 (la compatibilidad es lo primero que nota la gente).
2. Descubrimiento por mDNS + app compañera de Windows.
3. Plugin de Decky Loader.
4. Código de emparejamiento.
5. Plantilla de Steam Input, idiomas y fichas en las tiendas.
