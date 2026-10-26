# Rita en un Proyecto de Claude

Con esto Rita funciona dentro de la app de Claude (web, escritorio o celular), sin instalar nada y sin claves de ninguna API. La voz la pone la propia app.

## Qué hay en esta carpeta

- `instrucciones.md`: el personaje y las reglas. Va en "Instrucciones del proyecto".
- `conocimiento/`: lo que Rita tiene que saber del programa. Se suben como archivos del proyecto.
  - `programa.md`: ficha de SomosAsi, historia, público.
  - `piso-y-secciones.md`: quién está en el piso y el formato de cada sección.
  - `estilo-al-aire.md`: ejemplos de cómo suena y casos delicados.

Antes de subirlos, completá lo que está entre corchetes en `conocimiento/programa.md` y `conocimiento/piso-y-secciones.md`. Si quedan corchetes, Rita anda igual pero habla del programa en abstracto.

## Los cinco pasos

1. Crear el proyecto. En la app de Claude, entrá a "Proyectos" y tocá "Crear proyecto". Ponele de nombre "Rita" (o "Rita SomosAsi").
2. Pegar las instrucciones. Dentro del proyecto, abrí "Instrucciones del proyecto" (en la barra lateral o en la configuración del proyecto), pegá el contenido completo de `instrucciones.md` y guardá.
3. Subir los archivos. En la sección de archivos o conocimiento del proyecto, subí los tres archivos de la carpeta `conocimiento/`. Si después cambia algo del programa, editá el archivo y volvé a subirlo.
4. Abrir un chat dentro del proyecto. Siempre desde la pantalla del proyecto, para que tome las instrucciones y los archivos. Un chat abierto desde afuera no es Rita.
5. Tocar el ícono de voz. En la app de celular o de escritorio, al lado del cuadro de texto hay un ícono de micrófono u ondas de sonido: eso abre el modo de voz. Hablale como le hablarían al aire; Rita contesta hablando. Para cortarla, tocá la pantalla o decile "pará".

## Consejos para el aire

- Abrí un chat nuevo por programa. Así el historial no se mezcla con el de otro día.
- Si el chat empieza con la fecha ("hoy es viernes 30 de octubre, arrancamos"), Rita la usa para "hoy", "ayer" y "este finde".
- Si la app tiene búsqueda web activada, Rita busca lo que puede estar vencido (dólar, resultados, noticias). Si no la tiene, lo aclara.
- Probá antes de salir al aire con dos preguntas: una estable ("¿quién inventó el bidet?") y una de actualidad ("¿a cuánto está el dólar hoy?"). Fijate que responda en dos a cuatro oraciones, sin listas ni links.
