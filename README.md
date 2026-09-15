# Panel DCE

Panel público de solo lectura de la División Capacitación y Entrenamiento (DTOCE): https://leahalcon.github.io/panel-dce/

- `build.py` genera `index.html` a partir de `template.html`, leyendo el calendario de Google de la División (iCal) y la planilla de tareas (Google Sheets, CSV).
- `.github/workflows/build.yml` lo corre cada hora y publica el resultado en GitHub Pages. También se puede correr a mano desde la pestaña *Actions* → *Actualizar Panel DCE* → *Run workflow*.
- Secretos del repositorio: `DCE_ICS_URLS` (una o más direcciones iCal secretas, separadas por espacio) y `DCE_TASKS_CSV_URL` (URL de exportación CSV de la planilla).
