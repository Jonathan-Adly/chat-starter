from time import sleep
from colivara_py import Colivara
from django.core.management.base import BaseCommand
from pathlib import Path
import base64


class Command(BaseCommand):
    help = "Generate a summary of calls from the last 24 hours"

    def handle(self, *args, **kwargs):
      rag_client = Colivara(
        base_url="http://localhost:8001", api_key="m1TdGK5HeNRZjMbgClus0xCBsMuiyr8o"
      )
      # get all the documents under docs/ folder and upsert them to colivara
      documents_dir =  Path('docs')
      files = [f for f in documents_dir.glob('**/*') if f.is_file()]

      for file in files:
            with open(file, 'rb') as f:
                file_content = f.read()
                encoded_content = base64.b64encode(file_content).decode('utf-8')
                rag_client.upsert_document(name=file.name, document_base64=encoded_content, collection_name="mount sinai")
                sleep(0.5)
                self.stdout.write(self.style.SUCCESS(f"Document {file.name} uploaded successfully"))