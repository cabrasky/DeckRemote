<p align="center"><img src="deck/art/header.png" alt="DeckRemote" width="640"></p>

<p align="center"><b>Convierte tu Steam Deck en un mando inalámbrico para el PC, y ábrelo como cualquier juego de Steam.</b><br>
<a href="README.md">🇬🇧 Read in English</a></p>

---

Abres **DeckRemote** en la Steam Deck y tu PC con Windows detecta un **mando de Xbox 360 con cable**. Funciona por la red de casa (Wi‑Fi o cable). No hacen falta cables entre los dos, ni cacharros extra, ni servicios en segundo plano.

- **Funciona como cualquier mando de Xbox.** Windows usa su driver de serie *Xbox 360 Controller for Windows*, así que lo ve cualquier juego que hable **XInput**, además de Steam, los juegos con SDL y las webs de test de mandos.
- **Vibración.** Cuando un juego hace vibrar el mando, vibra la Deck (los dos motores, a través de la háptica de Steam).
- **También modo genérico.** Un interruptor de *Modo genérico* lo convierte en un mando HID normal (DirectInput), por si algún caso raro lo necesita.
- **La Deck sigue siendo tuya.** El botón Steam, el ⋯ y la pantalla táctil siguen funcionando en la Deck mientras juegas en el PC.
- **Usa tu configuración de Steam Input.** DeckRemote lee el mando que Steam da a los juegos, así que puedes asignar las palancas traseras, el giroscopio o los trackpads desde los ajustes del mando del acceso directo.
- **Nada funcionando de fondo.** No hay servicios al arrancar, y en el PC solo está el cliente USB/IP estándar. Todo se enciende al abrir la app y se apaga al cerrarla.

<p align="center">
  <img src="docs/img/deck-waiting-es.png" width="45%" alt="Esperando al PC">
  <img src="docs/img/deck-connected-es.png" width="45%" alt="Conectado al PC">
</p>

> Probado con SteamOS 3.9 (kernel 7.2 "neptune") y Windows 11 con usbip-win2 0.9.8.1.

## Cómo funciona

```
 Steam Deck                                                   PC con Windows
 ┌────────────────────────────────────────────┐              ┌───────────────────────────┐
 │ Steam Input ─► "Steam Virtual Gamepad"     │              │                           │
 │        ▲           │ SDL2                  │              │ usbip-win2 (cliente)      │
 │ vibra. │           ▼                       │   USB/IP     │            │              │
 │        └── App DeckRemote (raw-gadget)     │   TCP 3240   │            ▼              │
 │                    │  ▲                    │ ◄──────────► │ "Xbox 360 Controller      │
 │ mando Xbox 360 virtual en dummy_hcd,       │              │  for Windows" (XInput)    │
 │ publicado con usbip-host + usbipd          │              │ juegos ─► vibración ─┘    │
 └────────────────────────────────────────────┘              └───────────────────────────┘
```

1. DeckRemote es un "juego" más de Steam, así que Steam le pasa un mando virtual con tu configuración de Steam Input.
2. La app crea en el kernel de la Deck un **dispositivo USB virtual**: un mando de Xbox 360 con cable.
3. **USB/IP**, que ya viene de serie en SteamOS, publica ese dispositivo por la red.
4. El PC lo conecta con el cliente gratuito **usbip-win2**, y Windows lo trata como si hubieras enchufado un mando de Xbox por USB.
5. La vibración hace el camino de vuelta y la app la reproduce en la Deck.

Todos los detalles en [docs/es/ARQUITECTURA.md](docs/es/ARQUITECTURA.md).

## Qué necesitas

| Equipo | Necesita |
|---|---|
| Steam Deck | SteamOS 3.x. Ya trae `usbipd`, `usbip-host`, `dummy_hcd`, `raw_gadget` (modo Xbox), `usbip-vudc` + `usb_f_hid` (modo genérico), y Python 3 con Tk y SDL2. También necesitas **contraseña de sudo** (si nunca pusiste una, ejecuta `passwd` en Konsole). |
| PC | Windows 10/11 x64 con [usbip-win2](https://github.com/vadimgrn/usbip-win2), un cliente USB/IP con driver firmado por Microsoft. |
| Red | Los dos equipos en la misma red local, y el PC tiene que llegar al puerto TCP **3240** de la Deck. |

## Instalación

### 1. Steam Deck (solo una vez)

1. Pasa a **Modo Escritorio** y abre **Konsole**.
2. Bájate este repositorio en la Deck (con `git clone` o descargando el ZIP) y ejecuta:

   ```bash
   bash deck/install.sh
   ```

   El instalador:
   - copia la app a `~/DeckRemote/`;
   - instala el ayudante `/etc/deckremote/gadget.sh` y una regla de sudo que permite **solo** `gadget.sh up|up-xbox|bind|down|status` sin contraseña (te pide la contraseña de sudo una vez);
   - añade **DeckRemote** a tu biblioteca de Steam, con su arte (portada, banner, fondo y logo).
3. Vuelve al **Modo Juego**. DeckRemote estará en tu biblioteca, en *No de Steam*.

<p align="center"><img src="docs/img/deck-library.png" width="70%" alt="DeckRemote en la biblioteca de Steam"></p>

Si el instalador no pudo añadirlo a Steam, añádelo a mano. En Modo Escritorio abre Steam → *Juegos* → *Añadir un juego que no es de Steam* → *Examinar* → `~/DeckRemote/DeckRemote.desktop`. Después ejecuta `python3 ~/DeckRemote/set_artwork.py ~/DeckRemote/art` para poner el arte.

### 2. PC con Windows (solo una vez)

Abre PowerShell **como administrador** e instala el cliente USB/IP:

```powershell
winget install vadimgrn.usbip-win2
```

También puedes usar el instalador de [su página de releases](https://github.com/vadimgrn/usbip-win2/releases). Puede que Windows te pida reiniciar para cargar el driver.

## Cómo se usa

1. **Deck:** abre **DeckRemote**. La primera vez te pregunta el idioma (English / Español). Puedes cambiarlo cuando quieras con el botón de arriba a la derecha. La pantalla pone *Esperando al PC…* y muestra la IP de la Deck y el **bus id** que hay que conectar (por ejemplo `5-1`).

   <p align="center"><img src="docs/img/deck-language.png" width="60%" alt="Selector de idioma"></p>
2. **PC:** abre **USBip** desde el menú Inicio. Escribe la IP de la Deck en *Server* y pulsa *Add devices*. Elige el dispositivo que indica la Deck (*Microsoft Corp. : Xbox360 Controller*, con un bus id tipo `5-1`) y pulsa *Attach*. Desde una terminal:

   ```powershell
   & "C:\Program Files\USBip\usbip.exe" attach -r <ip-de-la-deck> -b 5-1
   ```

3. La Deck cambia a **● Conectado al PC** y muestra la IP de tu PC. Windows enciende el jugador 1 y el mando funciona en cualquier juego XInput. ¡A jugar!
4. Para terminar, toca **Desconectar y salir** en la Deck, o sal del juego desde Steam (⋯ / botón Steam → *Salir del juego*). El mando virtual y USB/IP se apagan solos, y el PC ve el mando desconectado.

<p align="center"><img src="docs/img/deck-connected-xbox-es.png" width="60%" alt="Conectado en modo Xbox 360"></p>

Para comprobarlo en Windows, mira en *Configuración → Bluetooth y dispositivos → Dispositivos*, ejecuta `joy.cpl` o usa cualquier web de test de mandos.

**Truco:** usbip-win2 sigue reintentando la conexión hasta que la desconectas. Si solo cierras DeckRemote en la Deck y no tocas USBip, lo normal es que el PC se reconecte solo la próxima vez que abras DeckRemote.

**Modo genérico:** el botón **⇄** de arriba a la izquierda cambia entre *Modo Xbox 360* (el de serie) y *Modo genérico* (un mando HID normal, que se conecta como `usbip-vudc.0`). La app recuerda lo que elijas.

### Qué botón es cada uno (modo Xbox 360)

Van uno a uno: A, B, X, Y, LB, RB, Back (Vista ⧉), Start (Menú ☰), los clics de los dos sticks, la cruceta, los dos sticks y los dos gatillos. Los botones Steam y ⋯ **se quedan en la Deck** (nunca se envían).

### Qué botón es cada uno (modo genérico)

| Deck (plantilla de mando de Steam Input) | Mando virtual en Windows |
|---|---|
| A, B, X, Y | Botones 1, 2, 3, 4 |
| L1 / R1 | Botones 5 / 6 |
| Vista (⧉) / Menú (☰) | Botones 7 / 8 |
| L3 / R3 (pulsar los sticks) | Botones 9 / 10 |
| Cruceta | Hat (POV) |
| Stick izquierdo | Ejes X / Y |
| Stick derecho | Ejes Rx / Ry |
| L2 / R2 | Ejes Z / Rz (0–255) |
| Steam, ⋯ | **Se quedan en la Deck** (no se envían) |

## Desinstalar

En la **Deck**, ejecuta `bash deck/uninstall.sh` en Konsole. Después quita el acceso *DeckRemote* de la biblioteca (Steam → *Administrar* → *Eliminar juego que no es de Steam*).

En el **PC**, ve a *Configuración → Aplicaciones → USBip → Desinstalar*.

## Si algo falla

| Qué pasa | Por qué / cómo se arregla |
|---|---|
| **"Mando: no detectado"** | Abre DeckRemote **desde Steam**. El "Steam Virtual Gamepad" solo existe cuando es Steam quien abre la app. |
| **"Sin compartir"** | El ayudante no arrancó. En Konsole, ejecuta `sudo -n /etc/deckremote/gadget.sh up-xbox` y mira el error. Si te pide contraseña, la regla de sudo no se está aplicando: el archivo tiene que ser `/etc/sudoers.d/zz-deckremote`. |
| El PC no ve el mando | La app tiene que estar abierta en la Deck. Revisa la IP y el bus id (la app muestra los dos) y el puerto: `Test-NetConnection <ip-de-la-deck> -Port 3240`. |
| USBip dice conectado pero no aparece ningún mando | Cierra y vuelve a abrir la app en la Deck, y haz *Attach* otra vez. Cada vez que cierras la app hay que reconectar. |
| No vibra | Comprueba que la vibración está activada en Steam (Ajustes → Mando) y en el juego. Los motores de la Deck son más suaves que los de un mando de Xbox. |
| La Deck no responde a sus propios botones | DeckRemote nunca toca el mando físico, así que no debería pasar. Si pasa, mantén pulsado el botón de encendido → *Reiniciar*. |
| Un juego no ve el mando en modo genérico | Vuelve al **Modo Xbox 360** (botón ⇄). |

## Seguridad

- **USB/IP no tiene contraseña ni cifrado.** Mientras la app está abierta, cualquier dispositivo de tu red local puede conectarse al mando virtual. Solo llega a ese mando, a nada más de la Deck. Úsalo en redes de confianza y ciérralo cuando acabes.
- La regla de sudo solo permite `/etc/deckremote/gadget.sh` con los argumentos fijos `up`, `up-xbox`, `bind`, `down` y `status`. El script es de root y no acepta nada más.

## Limitaciones

- Hay que hacer *Attach* en el PC cada vez que abres la app.
- El PC tiene que saber la IP de la Deck, así que mejor resérvala en el router.
- No hay giroscopio nativo. El giroscopio sí se puede asignar a un stick desde Steam Input.
- El modo Xbox 360 usa los identificadores USB de Microsoft (`045e:028e`), como hace cualquier mando compatible con XInput, para que Windows cargue su driver de serie. DeckRemote no tiene relación con Microsoft ni con Valve.

## Qué hay en el repositorio

```
deck/
  deckremote.py       la app (Python 3 + Tk + SDL2 vía ctypes), interfaz en inglés y español
  xinput.py           mando de Xbox 360 con raw-gadget: descriptores, informes y vibración
  gadget.sh           ayudante root: crea y quita el mando USB virtual y usbipd
  make_descriptor.py  genera el descriptor HID
  set_artwork.py      pone el arte de la biblioteca de Steam en el acceso directo
  install.sh          instalador para la Steam Deck
  uninstall.sh        desinstalador
  art/                arte de la biblioteca (portada, banner, fondo, logo, icono)
tools/
  make_art.py         regenera deck/art (Pillow)
docs/
  ARCHITECTURE.md / ROADMAP.md   documentación en inglés
  es/                            documentación en español
  img/                           capturas
```

### Desarrollo

- Ver la interfaz sin Deck: `python deck/deckremote.py --demo --windowed`. Recorre los estados con datos de ejemplo y no toca USB ni mandos.
- En la Deck, sin interfaz y con el estado por terminal: `python3 ~/DeckRemote/deckremote.py --headless`.
- Regenerar el arte: `python tools/make_art.py` (necesita Pillow).
