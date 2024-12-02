import os
import zipfile
import subprocess
import re
from flask import Flask, render_template, request, send_from_directory, flash
from werkzeug.utils import secure_filename
from tempfile import mkdtemp
import shutil

app = Flask(__name__)

# Configurazioni
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')  # Cartella per il file zip caricato
RESULTS_FOLDER = os.path.join(app.root_path, 'static', 'results')  # Cartella per i file PDF generati
ALLOWED_EXTENSIONS = {'md', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Per flash messages

# Funzione per verificare l'estensione del file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Verifica se la cartella di upload esiste, altrimenti crea
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Verifica se la cartella dei risultati esiste, altrimenti crea
if not os.path.exists(RESULTS_FOLDER):
    os.makedirs(RESULTS_FOLDER)
    os.chmod(RESULTS_FOLDER, 0o777)  # Forza i permessi di lettura, scrittura ed esecuzione sulla cartella

# Funzione per estrarre un file ZIP
def extract_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

# Funzione per gestire l'errore
def handle_conversion_error(stderr):
    # Esegui il controllo per i messaggi di errore specifici
    # Ignora l'errore relativo a `rsvg-convert`
    if re.search(r'rsvg-convert.*does not exist', stderr):
        return True  # Ignora questo errore
    # Ignora l'errore relativo al pacchetto `keyval`
    if re.search(r'Package keyval Error: bottom:1.5cm undefined', stderr):
        return True  # Ignora questo errore
    # Se ci sono altri errori, non ignorarli
    return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Verifica che il file sia caricato
        if 'file' not in request.files:
            flash('Nessun file caricato!', 'error')
            return render_template('index.html')

        file = request.files['file']
        
        # Verifica se il file è valido
        if file.filename == '':
            flash('Nessun file selezionato!', 'error')
            return render_template('index.html')
        
        if file and file.filename.endswith('.zip'):
            # Sicurezza nel salvataggio del nome del file
            filename = secure_filename(file.filename)
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Salva il file ZIP
                file.save(zip_path)

                # Crea una cartella temporanea per estrarre il contenuto
                temp_dir = mkdtemp()

                # Estrai il contenuto del file ZIP
                extract_zip(zip_path, temp_dir)

                # Elimina il file ZIP appena estratto
                os.remove(zip_path)

                # Lista dei file MD e immagini trovati
                md_files = []
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.md'):
                            md_files.append(os.path.join(root, file))

                if not md_files:
                    flash('Nessun file Markdown trovato nel ZIP.', 'error')
                    return render_template('index.html')

                # Inizializza il contatore per il PDF
                counter = 1
                output_files = []

                # Processa i file Markdown
                for md_file in md_files:
                    # Costruisce il percorso temporaneo per il file
                    temp_md_file = f"{md_file}_temp.md"
                    
                                        # Rimuove il contenuto specificato (Open in Codespaces) e le immagini SVG
                    with open(md_file, 'r') as f:
                        content = f.read()

                    # Rimuovi i riferimenti Open in Codespaces
                    content = content.replace('[!\\[Open in Codespaces\\]\\([\\^\\)]*\\)', '')

                    # Rimuovi le immagini SVG
                    content = content.replace('![', '').replace('.svg', '')  # Rimuove tutte le immagini SVG

                    # Scrivi il contenuto modificato in un file temporaneo
                    with open(temp_md_file, 'w') as f:
                        f.write(content)

                    # Costruisce il comando per LaTeX usando pandoc
                    # Comando aggiornato per il pdf
                    command = f"""
                    $content = Get-Content '{md_file}'
                    $content = $content -replace '\\[!\\[Open in Codespaces\\]\\([\\^\\)]*\\)', ''
                    $content | Set-Content -Path '{temp_md_file}'
                    pandoc -V geometry:"top=2cm,bottom=1.5cm,left=2cm,right=2cm" -f markdown-implicit_figures --pdf-engine=xelatex -o '{os.path.join(app.config['RESULTS_FOLDER'], f"{counter}.pdf")}' '{temp_md_file}'
                    Remove-Item '{temp_md_file}'
                    """

                    
                    # Esegui il comando
                    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    # Verifica l'errore
                    if result.returncode != 0:
                        stderr = result.stderr.decode()
                        flash(f"Errore durante la conversione: {stderr}", 'error')
                        return render_template('index.html')

                    # Verifica se il PDF è stato creato
                    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], f"{counter}.pdf")
                    if not os.path.isfile(pdf_path):
                        flash(f"Errore nella creazione del PDF: {pdf_path}", 'error')
                        return render_template('index.html')

                    # Aggiungi il file PDF all'elenco
                    output_files.append(f'{counter}.pdf')
                    counter += 1

                    # Elimina il file temporaneo
                    os.remove(temp_md_file)

                # Elimina la cartella temporanea
                shutil.rmtree(temp_dir)

                # Restituisci i file PDF per il download
                return render_template('index.html', output_files=output_files)

            except Exception as e:
                flash(f"Errore: {e}", 'error')
                return render_template('index.html')

        else:
            flash('Carica un file ZIP contenente file .md e immagini.', 'error')
            return render_template('index.html')

    return render_template('index.html')

# Route per il download dei file generati
@app.route('/static/results/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['RESULTS_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)
