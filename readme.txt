How to download model:

1. Sign up to Huggingface 
2. Request access here: https://huggingface.co/google/paligemma-3b-mix-448
3. On the machine or the VM - download the model via  byaldi



# we have to login before we can get the model
RAG = RAGMultiModalModel.from_pretrained("vidore/colpali")
RAG.index(
    input_path="docs/", # The path to your documents
    index_name=demo_files, # The name you want to give to your index. It'll be saved at `index_root/index_name/`.
    store_collection_with_index=True, # Whether the index should store the base64 encoded documents.
    metadata=metadata, # Optionally, you can specify a list of metadata for each document. They must be a list of dictionaries, with the same length as the number of documents you're passing.
    overwrite=True 
)
