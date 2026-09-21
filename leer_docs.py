from pypdf import PdfReader
import os

print("=== INICIANDO LECTURA DE PDFs ===")
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".pdf") and "zlib" not in root:
            ruta = os.path.join(root, file)
            print(f"\n--- LEYENDO: {file} ---")
            try:
                reader = PdfReader(ruta)
                texto = ""
                for i, page in enumerate(reader.pages):
                    texto += f"[Pag {i+1}] " + (page.extract_text() or "")
                # Imprime solo los primeros 3000 caracteres
                print(texto[:3000]) 
                if len(texto) > 3000: 
                    print("\n... (texto truncado, revisa el PDF manualmente si es necesario) ...")
            except Exception as e:
                print(f"Error leyendo {file}: {e}")
