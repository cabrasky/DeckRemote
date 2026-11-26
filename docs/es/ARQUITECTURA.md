# Arquitectura

[🇬🇧 English version](../ARCHITECTURE.md)

DeckRemote tiene dos modos. El **modo Xbox 360** (el de serie) se presenta como un mando de Xbox 360 con cable, así que Windows usa XInput y los juegos pueden mandar vibración. El **modo genérico** se presenta como un mando HID normal.

## Piezas

| Pieza | Dónde | Quién la ejecuta | Qué hace |
|---|---|---|---|
| `deckremote.py` | `~/DeckRemote/` | `deck`, lanzado por Steam | Lee el mando, alimenta el mando virtual, reproduce la vibración y muestra la pantalla de estado |
| `xinput.py` | `~/DeckRemote/` | `deck` | Mando de Xbox 360 con raw-gadget: descriptores USB, peticiones de control, informes de entrada y paquetes de vibración |
| `gadget.sh` | `/etc/deckremote/` | `root` vía `sudo -n` | `up-xbox` / `bind` (modo Xbox), `up` (modo genérico), `down` (lo quita todo), `status` (`off` / `waiting` / `connected` + bus id) |
| `report_desc.bin`, `report_len` | `~/DeckRemote/` | — | El descriptor HID del modo genérico, generado por `make_descriptor.py` |
| `set_artwork.py` | `~/DeckRemote/` | `deck` | Busca el app id del acceso directo en `shortcuts.vdf` y copia el arte en `userdata/<usuario>/config/grid/` |
| usbip-win2 | PC | usuario | Cliente USB/IP |

## Modo Xbox 360

1. Steam lanza `deckremote.sh`, que ejecuta `deckremote.py` con el entorno de juego de Steam: Steam Input está activo y el mando físico queda oculto para SDL.
2. La app ejecuta `sudo -n gadget.sh up-xbox`, que carga `usbip-host`, `dummy_hcd` y `raw_gadget`, apunta el puerto de dummy_hcd (por ejemplo `5-1`) en la lista de usbip-host y da `/dev/raw-gadget` al usuario `deck`.
3. `xinput.py` abre `/dev/raw-gadget`, se engancha a `dummy_udc.0` y empieza a contestar peticiones USB como un mando de Xbox 360 con cable (`045e:028e`, interfaz de fabricante `FF/5D/01` con su descriptor `0x21` de 17 bytes y dos endpoints de interrupción). Los descriptores siguen a GP2040-CE (MIT).
4. La propia Deck enumera el dispositivo nuevo primero. Su `SET_CONFIGURATION` se rechaza, así que el mando nunca se configura en local: ni `xpad`, ni mando fantasma en Steam.
5. La app ejecuta `gadget.sh bind`: `usbip bind` pasa el dispositivo a usbip-host y `usbipd` (modo host) lo publica en el puerto TCP 3240.
6. El PC lo conecta. Windows lo configura, carga su driver de serie *Xbox 360 Controller for Windows*, pide las capacidades XInput (las contesta `xinput.py`) y enciende el LED de jugador.
7. Un hilo lee el **"Steam Virtual Gamepad"** con SDL2 cada 4 ms. Monta el informe XInput de 20 bytes (botones, gatillos y sticks con el eje Y invertido) y lo envía por el endpoint IN en cada cambio, más uno de mantenimiento cada 0,5 s.
8. Los paquetes de vibración (`00 08 00 fuerte suave …`) llegan por el endpoint OUT. La app los reproduce en la Deck con `SDL_GameControllerRumble` y los rearma cada 0,5 s mientras no sean cero, porque XInput mantiene un nivel hasta que cambia y la vibración de SDL caduca. La vibración se pone a cero cuando el PC se desconecta y al salir de la app.

### Informe XInput (20 bytes)

| Byte | Contenido |
|---|---|
| 0, 1 | `00 14` (tipo, longitud) |
| 2 | Cruceta arriba/abajo/izquierda/derecha, Start, Back, LS, RS |
| 3 | LB, RB, Guide, –, A, B, X, Y |
| 4, 5 | Gatillo izquierdo / derecho (0..255) |
| 6–13 | LX, LY, RX, RY (int16, Y hacia arriba = positivo) |
| 14–19 | 0 |

## Modo genérico

1. `gadget.sh up` carga `libcomposite`, `usb_f_hid` y `usbip-vudc`, crea en configfs un gadget `1d6b:0104` con una función HID de 13 bytes, lo enlaza a `usbip-vudc.0`, arranca `usbipd --device` y da `/dev/hidg0` a `deck`.
2. La app escribe en `/dev/hidg0` informes HID de 13 bytes (16 botones, hat, 4 ejes y 2 gatillos), sin bloquear, en cada cambio y como mínimo cada 100 ms.

## Común a los dos modos

- La interfaz (Tk a pantalla completa) consulta `gadget.sh status` cada segundo y muestra la IP del PC, que saca con `ss` de las conexiones al puerto 3240.
- Al salir (con el botón, con el `SIGTERM` de Steam o cerrando la ventana), la app para la vibración, envía un informe neutro y ejecuta `gadget.sh down`.
- Si la app muere sin poder recoger (Steam se reinicia, `SIGKILL`), la pilla un pequeño **vigilante**: una unidad de usuario temporal `deckremote-guard-<pid>` que arranca con la app, espera a que desaparezca su PID, ejecuta `gadget.sh down` y se cierra. Nunca dura más de ~2 segundos después de la app.
- El botón **⇄** guarda el otro modo y reinicia la app en el sitio (`execv`, mismo PID para Steam).

## Interfaz

- La pantalla sigue el diseño *Holograma*: la Deck proyecta un mando holográfico que ilumina los botones que pulsas, sigue los dos sticks y se atenúa mientras no hay ningún PC conectado. Una tarjeta de cristal muestra el estado, las IPs, el bus id, el modo y la vibración de los dos motores.
- En la Deck no hay Pillow y Tk dibuja las formas sin suavizado, así que `tools/make_ui.py` renderiza de antemano, a 3×, cada pieza visual en `deck/ui/` (fondo, holograma encendido y atenuado, un brillo por botón, el punto del stick, la tarjeta, los botones, las fichas de idioma, los puntos de estado y los logotipos) y guarda en `deck/ui/layout.json` las posiciones que necesita la app. La app solo coloca esos PNG en un lienzo de Tk y escribe el texto con Noto Sans (que incluye CJK).
- El visor de entrada se refresca a ~30 fps y solo toca los elementos que han cambiado.
- Los textos están en `deck/i18n.py` (12 idiomas). La primera vez, el selector resalta el idioma que tengas en Steam (`registry.vdf`).
- Todo se maneja con la pantalla táctil, porque los botones de la Deck se están enviando al PC.

## Decisiones de diseño

### ¿Por qué no enviar el mando físico de la Deck?
El primer prototipo prestaba por USB/IP el mando real (`28de:1205`). No funcionaba bien:
- Windows lo ve como teclado, ratón y un dispositivo de Valve. No es un mando de juego salvo que Steam esté abierto en el PC.
- Los botones **Steam** y **⋯** son parte de ese mismo dispositivo, así que la Deck se quedaba sin ellos, y sin forma de salir.
- Al devolverlo, Steam de la Deck podía no volver a cogerlo hasta reiniciar.

Por eso DeckRemote **crea un mando virtual nuevo**, y la Deck conserva el suyo.

### ¿Por qué solo el "Steam Virtual Gamepad"?
- Así respeta tu configuración de Steam Input, y los botones Steam / ⋯ siguen siendo de Steam.
- La app desactiva HIDAPI en SDL (`SDL_JOYSTICK_HIDAPI=0`) y elige el mando **por nombre**, porque Steam lo anuncia con el mismo VID:PID que el mando físico. Abrir el mando físico directamente puede dejarlo en un estado que Steam no recupera.

### ¿Por qué raw-gadget sobre dummy_hcd en el modo Xbox?
- El driver XInput de Windows necesita el descriptor de fabricante de 17 bytes de tipo `0x21`. **FunctionFS** valida el tipo `0x21` como un descriptor HID de 9 bytes y lo rechaza. Sin él, Windows carga el driver pero XInput dice que el mando *no está conectado*.
- **raw-gadget** deja que la app conteste ella misma a cada petición. Pero `usbip-vudc` pide el descriptor del dispositivo de forma síncrona, y una respuesta desde el espacio de usuario no llega a tiempo.
- Así que el mando vive en **dummy_hcd** (un puerto USB virtual local) y se publica con **usbip-host**, el mismo camino que USB/IP usa para dispositivos reales.
- Probado en SteamOS 3.9: desmontar un gadget a medio configurar (vudc con FunctionFS o con raw-gadget) y descargar esos módulos **colgó el kernel**. Por eso el ayudante nunca descarga `raw_gadget` ni `dummy_hcd`. Se quedan cargados sin hacer nada, y nada escucha en la red.

### ¿Por qué el archivo de sudo se llama `zz-deckremote`?
`sudo` lee `/etc/sudoers.d/` en orden alfabético y aplica la **última** regla que coincide. SteamOS trae `wheel`, que pide contraseña. Un nombre que vaya detrás garantiza que gane la regla `NOPASSWD`.

### Nada de fondo
No hay servicios al arrancar, ni reglas udev, ni tareas en el PC. `usbipd` solo existe mientras la app está abierta. En el PC solo hace falta el cliente USB/IP estándar.

## Persistencia en SteamOS
- `~/DeckRemote` vive en `/home`, que las actualizaciones de SteamOS nunca tocan.
- `/etc/deckremote` y `/etc/sudoers.d/zz-deckremote` viven en `/etc`, que SteamOS conserva entre actualizaciones (overlay). Si alguna actualización grande los borrara, basta con volver a ejecutar `install.sh`.

## Arte
`tools/make_art.py` dibuja todas las imágenes de la biblioteca con Pillow, de forma procedural y con supermuestreo 3×. Las siluetas de la Deck y del mando se ajustaron contra referencias frontales con `tools/shape_compare.py`, que calcula la coincidencia (IoU) y genera una superposición en color.
