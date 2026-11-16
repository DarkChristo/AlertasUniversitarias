INSTRUCCIONES PARA EJECUTAR EL SISTEMA:
1. Configuración Inicial y Requisitos
Antes de iniciar la aplicación, asegúrese de cumplir con los siguientes requisitos en todos los equipos (emisor y receptores) para garantizar la comunicación mediante IP multicast: 
•	Red Local: Conecte todos los equipos a la misma red (se recomienda un hotspot Wi-Fi en la banda de 2,4 GHz). 
•	Sincronización: Sincronice los relojes de los equipos (Configuración → Hora e idioma → Sincronizar ahora). 
•	Firewall: Otorgue permisos a Python en el firewall del sistema operativo, tanto para redes públicas como privadas. 
•	Ejecución: Abra una terminal en la carpeta del proyecto y ejecute el comando python app.py. 
2. Uso del Sistema: Rol Emisor (Seguridad)
Este perfil está diseñado para el personal encargado de enviar los avisos institucionales a la comunidad.
•	Inicio de sesión: En la pantalla de login, ingrese el usuario seguridad y su contraseña autorizada (si es incorrecta, el sistema denegará el acceso). 
•	Panel de control: Una vez dentro, visualizará el panel de envío.
•	Envío de alertas:
•	Seleccione el nivel de la alerta y una plantilla prestablecida (por ejemplo, nivel crítico: "Laboratorios, fuga de gas") o redacte una de nivel aviso o informativa. 
•	Haga clic en el botón Enviar alerta. El mensaje se enviará una sola vez al grupo multicast. 
•	Pruebas de ráfaga: Para evaluar la red, puede utilizar la función de ráfaga configurando una cantidad (ej. 30 alertas) y un intervalo (ej. 200 ms). 
•	Estado: Mientras el emisor esté abierto, enviará automáticamente "latidos" (heartbeats) cada segundo para que los receptores sepan que está en línea. 
3. Uso del Sistema: Rol Receptor (Estudiantes)
Este perfil corresponde a los usuarios que reciben las notificaciones en sus equipos.
1.	Inicio de sesión: Ingrese sus credenciales de usuario (por ejemplo, estudiante1, estudiante2 o estudiante3). 
2.	Configuración de interfaz: En el campo «IP de mi interfaz», escriba la dirección IP de su adaptador Wi-Fi (ej. 192.168.137.x). La pantalla pasará al estado "Esperando alertas". 
3.	Visualización de alertas: Las notificaciones aparecerán de inmediato. Si la alerta es de nivel crítico, se mostrará resaltada en un banner de color rojo. 
4.	Panel de estadísticas: La interfaz mostrará en tiempo real:
o	Recibidas: Total de alertas que han llegado con éxito. 
o	Huecos: Contador de paquetes perdidos (basado en los números de secuencia y los latidos del emisor). 
o	Duplicados: Alertas recibidas más de una vez. 
o	Estado: Un indicador visual dirá «Emisor: ACTIVO» si se están recibiendo los latidos. 
1.	Simulación de fallas: Para realizar pruebas, ingrese un porcentaje en el campo Pérdida simulada (ej. 30) y presione Aplicar. Esto forzará al sistema a descartar temporalmente esa proporción de alertas. 
4. Solución de Problemas Frecuentes
•	El receptor no recibe alertas: Verifique que la dirección ingresada en «IP de mi interfaz» sea correcta. Compruebe que la red Wi-Fi esté transmitiendo en 2,4 GHz (en redes de 5 GHz hay alta pérdida de paquetes) y confirme que el firewall no esté bloqueando a Python. 
•	Alertas no deseadas o rechazadas: Si alguien intenta enviar alertas sin estar autorizado (intruso), el sistema las ignorará gracias a la validación de firma HMAC y el contador de Rechazadas aumentará en la pantalla. 
•	Fallas de reconexión: Si se desconecta y reconecta el Wi-Fi abruptamente, es posible que el adaptador de red no recupere el grupo multicast de inmediato. En caso de persistir, reinicie la aplicación
5. Consideraciones Técnicas y Limitaciones
Para comprender el alcance y funcionamiento interno del Sistema de Alertas Universitarias, los usuarios y administradores deben tener en cuenta los siguientes aspectos técnicos:
•	Eficiencia de red (Multicast): El sistema está diseñado para que el costo del emisor no crezca con el número de equipos. Una alerta se envía una sola vez a la red y es recibida simultáneamente por todos los usuarios suscritos al grupo. 
•	Garantía de entrega (UDP): El protocolo subyacente prioriza la velocidad y no garantiza la entrega de todos los paquetes. Aunque el sistema no recupera lo perdido, utiliza números de secuencia y latidos constantes para detectar y medir exactamente qué información no llegó. 
•	Ausencia de retransmisión: En la versión actual de la aplicación no existen reenvíos automáticos. Si la red falla severamente (por ejemplo, al usar bandas inestables de 5 GHz 
en lugar de las recomendadas de 2,4 GHz), la pérdida se registra pero no se recupera. La adición de confirmaciones negativas (NACK) se contempla como una mejora futura. 
•	Gestión de credenciales: El inicio de sesión se realiza de forma local en cada equipo y la clave de firma de seguridad (HMAC) se encuentra almacenada en un archivo de configuración, por lo que no se depende de un servidor central de usuarios.







# Sistema de alertas universitarias con multicast

Proyecto final de Sistemas Distribuidos. Una aplicación con interfaz gráfica (Tkinter, Python) donde un
usuario con rol **emisor** envía alertas a un grupo **multicast UDP** y todos los usuarios con rol
**receptor** que están unidos al grupo las reciben a la vez, desde varios equipos de la misma red.

## Requisitos

- Python 3.10 o superior (Tkinter viene incluido con el instalador de python.org; en Windows marcar "Add Python to PATH").
- No hay que instalar ninguna biblioteca adicional: solo se usa la biblioteca estándar
  (`socket`, `struct`, `threading`, `queue`, `tkinter`, `json`, `csv`, `hashlib`, `hmac`).
- Todos los equipos en la **misma red local** (por ejemplo, el hotspot de uno de los portátiles; si se usa Wi-Fi
  de 5 GHz algunos adaptadores pierden el multicast, por eso se recomienda la banda de **2,4 GHz**).

## Estructura

```
alertas-multicast/
├── README.md
├── config.json            grupo multicast, puerto, TTL y clave de firma
├── data/
│   ├── usuarios.json      usuarios, roles y contraseñas (guardadas como hash)
│   └── alertas_prueba.json  alertas de ejemplo (plantillas y ráfagas)
├── src/
│   ├── app.py             aplicación con interfaz (login + pantallas por rol)
│   ├── net.py             motor de red: emisor y receptor multicast
│   ├── auth.py            inicio de sesión
│   ├── common.py          configuración, codificación JSON y firma HMAC
│   ├── make_user.py       crear usuarios nuevos
│   ├── sender.py          emisor por línea de comandos (pruebas de ráfaga)
│   ├── receiver.py        receptor por línea de comandos (pruebas, --drop-rate)
│   └── analyze.py         análisis de los CSV de las pruebas
├── logs/                  CSV que genera cada receptor
└── evidencias/            capturas y .pcapng de las pruebas
```

## Cómo ejecutar

1. Copiar la carpeta completa a cada equipo (ruta sencilla, sin espacios, por ejemplo `C:\proyectos\alertas-multicast`).
2. Conectar todos los equipos a la misma red y anotar la IP de cada uno (`ipconfig`, adaptador Wi-Fi).
3. En cada equipo, desde la carpeta `src`:

   ```
   python app.py
   ```
4. Iniciar sesión. En el campo **IP de mi interfaz** poner la IP del adaptador de red por el que está conectado
   (por ejemplo `192.168.137.35`). Si se deja una IP equivocada, el multicast sale o entra por otro adaptador y no funciona.
5. Un equipo entra como **emisor** y los demás como **receptores**. Primero entran los receptores y después el emisor.

### Usuarios de ejemplo

| Usuario | Contraseña | Rol |
|---|---|---|
| seguridad | Alerta2026 | emisor |
| estudiante1, estudiante2, estudiante3, docente | Campus2026 | receptor |

Para crear otro usuario: `python make_user.py <usuario> <emisor|receptor> "<Nombre>" <contraseña>`.

## Qué hace cada rol

- **Emisor:** elige una plantilla o escribe nivel, zona y mensaje, y pulsa *Enviar alerta*. También puede enviar una
  *ráfaga de prueba*. Cada alerta se envía **una sola vez** al grupo `239.255.1.1:5007`. Además manda un *latido*
  por segundo con el último número de secuencia enviado.
- **Receptor:** al iniciar sesión se une al grupo (`IP_ADD_MEMBERSHIP`). Muestra las alertas con color según el nivel,
  y contadores de recibidas, huecos (pérdidas), duplicados, fuera de orden, descartadas (simuladas) y rechazadas (firma
  inválida). Indica si el emisor está activo según los latidos. Al cerrar sesión deja el grupo (IGMP Leave).
  El recuadro **Prueba de falla** descarta un porcentaje de paquetes en la aplicación para simular pérdida.

## Dónde está el multicast en el código

- `src/net.py`, clase `AlertSender`: `sock.sendto(mensaje, (grupo, puerto))` con `IP_MULTICAST_TTL`, `IP_MULTICAST_IF`.
- `src/net.py`, clase `AlertReceiver`: `setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)` y `IP_DROP_MEMBERSHIP` al salir.

## Confiabilidad y seguridad

Multicast sobre UDP no garantiza entrega, orden ni ausencia de duplicados. Por eso cada alerta lleva un número de
secuencia (`seq`) y un identificador de sesión, y el emisor envía latidos para que el receptor detecte la pérdida
de los últimos mensajes. No hay retransmisión: las pérdidas se detectan y se miden, no se recuperan.
Cada mensaje va firmado con HMAC-SHA256 usando la clave de `config.json`; los receptores rechazan lo que no tenga
firma válida. El inicio de sesión es local en cada equipo (no hay servidor central de usuarios).

## Pruebas y análisis

Cada receptor guarda un CSV en `logs/` por cada sesión del emisor. Para analizar una prueba, reunir los CSV de
todos los receptores en una carpeta (por ejemplo `logs/prueba1`) y ejecutar desde `src`:

```
python analyze.py ../logs/prueba1 --total 100
```

Ráfagas y pérdida simulada por línea de comandos:

```
python sender.py --count 1000 --interval 0.001 --iface 192.168.137.1
python receiver.py --node pc3 --iface 192.168.137.35 --drop-rate 0.2
```

## Solución de problemas

- **No llega nada:** revisar la IP de interfaz, el firewall de Windows (permitir Python en redes públicas y privadas)
  y la banda del hotspot (2,4 GHz).
- **Aparecen "rechazadas":** el emisor usa otra clave; todos los equipos deben tener el mismo `config.json`.
- **Error de red al ingresar:** la IP escrita no pertenece a ningún adaptador del equipo.

## Fuentes, bibliotecas y código de terceros

Completar con las referencias del informe (RFC 1112, RFC 3376, documentación de Python `socket` y `tkinter`)
y declarar el uso de herramientas de apoyo según lo que indique la asignatura.
