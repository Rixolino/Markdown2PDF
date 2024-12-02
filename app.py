from flask import Flask, render_template, request, send_from_directory
import os
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'md'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Verifica che il file sia caricato e valido
        if 'file' not in request.files:
            return 'Nessun file caricato', 400
        file = request.files['file']
        if file and allowed_file(file.filename):
            # Sicurezza nel salvataggio del nome del file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Comando Pandoc per la conversione
            output_filename = filename.rsplit('.', 1)[0] + '.pdf'
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

            # Esegui la conversione di Pandoc (con il comando per escludere il testo indesiderato)
            command = f"pandoc -V geometry:'top=2cm, bottom=1.5cm, left=2cm, right=2cm' -f markdown-implicit_figures -o '{output_path}' '{file_path}'"
            subprocess.run(command, shell=True, check=True)

            return send_from_directory(app.config['UPLOAD_FOLDER'], output_filename, as_attachment=True)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
