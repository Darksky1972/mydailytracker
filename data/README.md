# Carpeta de datos

Pon aquí tu export de Whoop (los CSV) y la app los cargará automáticamente
cuando la base de datos esté vacía, y con el botón **📂 Importar desde /data**
en la barra lateral.

Archivos reconocidos (vale con uno o varios):

- `physiological_cycles.csv`
- `journal_entries.csv`
- `workouts.csv`
- `sleeps.csv`

Así no tienes que volver a subirlos a mano: aunque borres `senal.db`, al abrir
la app se reconstruyen tus datos reales desde estos archivos.

Estos CSV contienen datos personales de salud, por eso están excluidos de git
(ver `.gitignore`). Esta carpeta y este README sí se mantienen.
