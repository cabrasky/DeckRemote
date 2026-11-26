# Arquitectura

[🇬🇧 English version](../ARCHITECTURE.md)

## Piezas

| Pieza | Dónde | Quién la ejecuta | Qué hace |
|---|---|---|---|
| `deckremote.py` | `~/DeckRemote/` | `deck`, lanzado por Steam | Lee el mando, escribe los informes HID y muestra la pantalla de estado |
| `gadget.sh` | `/etc/deckremote/` | `root` vía `sudo -n` | `up` crea el mando USB virtual y arranca `usbipd --device`. `down` lo quita todo. `status` devuelve `off` / `waiting` / `connected`. |
| `report_desc.bin`, `report_len` | `~/DeckRemote/` | — | El descriptor HID del mando, generado por `make_descriptor.py` |
| `set_artwork.py` | `~/DeckRemote/` | `deck` | Busca el app id del acceso directo en `shortcuts.vdf` y copia el arte en `userdata/<usuario>/config/grid/` |
| usbip-win2 | PC | usuario | Cliente USB/IP que conecta `usbip-vudc.0` |

## Qué pasa al abrir la app

1. Steam lanza `deckremote.sh`, que ejecuta `deckremote.py` con el entorno de juego de Steam: Steam Input está activo y `SDL_GAMECONTROLLER_IGNORE_DEVICES` oculta el mando físico.
2. La app ejecuta `sudo -n gadget.sh up`, que:
   - carga `libcomposite`, `usb_f_hid` y `usbip-vudc`;
   - crea en configfs (`/sys/kernel/config/usb_gadget/deckremote`) un dispositivo USB `1d6b:0104` con una función HID de 13 bytes;
   - lo enlaza al UDC virtual `usbip-vudc.0`;
   - arranca `usbipd --device` como unidad temporal (`deckremote-usbipd`), que publica ese UDC en el puerto TCP 3240;
   - da `/dev/hidg0` al usuario `deck`.
3. Un hilo abre con SDL2 el **"Steam Virtual Gamepad"**, el mando que Steam da a los juegos. Cada 4 ms escribe en `/dev/hidg0` botones, cruceta, sticks y gatillos: en cada cambio, y como mínimo cada 100 ms. La escritura no bloquea, así que la interfaz no se congela aunque no haya ningún PC conectado.
4. La interfaz (Tk a pantalla completa) consulta `gadget.sh status` cada segundo. Cuando hay un PC conectado muestra su IP, que saca con `ss` de las conexiones al puerto 3240.
5. Al salir (con el botón, con el `SIGTERM` de Steam o cerrando la ventana), la app envía un informe neutro y ejecuta `gadget.sh down`.

## Informe HID (13 bytes, sin report ID)

| Bytes | Campo | Rango |
|---|---|---|
| 0–1 | 16 botones (bit 0 = A …) | 0/1 |
| 2 | Hat en el nibble bajo (0–7, 8 = centro) | — |
| 3–4, 5–6 | Stick izquierdo X, Y | −32767..32767 |
| 7–8, 9–10 | Stick derecho Rx, Ry | −32767..32767 |
| 11, 12 | Gatillos Z, Rz | 0..255 |

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

### ¿Por qué `usbip-vudc` y no `dummy_hcd`?
Con `usbip-vudc` el dispositivo virtual nunca aparece como USB local en la Deck, así que ningún driver de la Deck lo coge, y `usbipd --device` lo publica directamente.

### ¿Por qué el archivo de sudo se llama `zz-deckremote`?
`sudo` lee `/etc/sudoers.d/` en orden alfabético y aplica la **última** regla que coincide. SteamOS trae `wheel`, que pide contraseña. Un nombre que vaya detrás garantiza que gane la regla `NOPASSWD`.

### Nada de fondo
No hay servicios al arrancar, ni reglas udev, ni tareas en el PC. `usbipd` solo existe mientras la app está abierta. En el PC solo hace falta el cliente USB/IP estándar.

## Persistencia en SteamOS
- `~/DeckRemote` vive en `/home`, que las actualizaciones de SteamOS nunca tocan.
- `/etc/deckremote` y `/etc/sudoers.d/zz-deckremote` viven en `/etc`, que SteamOS conserva entre actualizaciones (overlay). Si alguna actualización grande los borrara, basta con volver a ejecutar `install.sh`.

## Arte
`tools/make_art.py` dibuja todas las imágenes de la biblioteca con Pillow, de forma procedural y con supermuestreo 3×. Las siluetas de la Deck y del mando se ajustaron contra referencias frontales con `tools/shape_compare.py`, que calcula la coincidencia (IoU) y genera una superposición en color.
