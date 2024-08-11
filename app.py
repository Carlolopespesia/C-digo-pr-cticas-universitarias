import streamlit as st
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from upload_data import cargar_documentos, crear_vectorstore
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
import ollama
import os
import shutil
import time
from streamlit_autorefresh import st_autorefresh


# Códigos de escape ANSI para colores
AZUL = "\033[94m"
VERDE = "\033[92m"
RESET = "\033[0m"

def iniciar_chat(ruta_archivo, MODELO, borrar):
    if not borrar:
        st.write("Iniciando chat con el modelo:", MODELO)
        llm = Ollama(model=MODELO)
        embed_model = FastEmbedEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        vectorstore = Chroma(embedding_function=embed_model,
                            persist_directory="chroma_db_dir",
                            collection_name="stanford_report_data")
        total_rows = len(vectorstore.get()['ids'])
        st.write("Total rows in vectorstore:", total_rows)
        if total_rows == 0:
            docs = cargar_documentos(ruta_archivo)
            vectorstore = crear_vectorstore(docs)
        retriever = vectorstore.as_retriever(search_kwargs={'k': 4})

        custom_prompt_template = """Use the following pieces of information to answer the user's question.
        If you don't know the answer, just say that you don't know, don't try to make up an answer.

        Context: {context}
        Question: {question}

        Only return the helpful answer below and nothing else but in spanish.
        Helpful answer:
        """
        prompt = PromptTemplate(template=custom_prompt_template, input_variables=['context', 'question'])

        qa = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )

        return qa
    else:
        embed_model = FastEmbedEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = Chroma(embedding_function=embed_model,
                            persist_directory="chroma_db_dir",
                            collection_name="stanford_report_data")
        vectorstore.delete_collection()
        limpiar_chroma_db()

        
def es_carpeta_vacia(ruta_carpeta):
    # Verificar si la carpeta existe
    if not os.path.exists(ruta_carpeta):
        return False

    # Listar los archivos en la carpeta
    archivos = os.listdir(ruta_carpeta)

    # Verificar si la lista de archivos está vacía
    return len(archivos) == 0

def eliminar_contenido_carpeta(carpeta):
    if es_carpeta_vacia(carpeta):
        return
    else:
        for archivo in os.listdir(carpeta):
            ruta_archivo = os.path.join(carpeta, archivo)
            try:
                if os.path.isfile(ruta_archivo) or os.path.islink(ruta_archivo):
                    os.unlink(ruta_archivo)  # Elimina archivos y enlaces simbólicos
                elif os.path.isdir(ruta_archivo):
                    shutil.rmtree(ruta_archivo)  # Elimina carpetas y su contenido
            except:
                pass

            
def limpiar_chroma_db():
    directory = "chroma_db_dir"
    if os.path.exists(directory):
        try:
            # Esperar un poco antes de intentar borrar
            time.sleep(2)
            shutil.rmtree(directory)
            print("Directorio Chroma borrado con éxito.")
        except OSError as e:
            print(f"Error : {e}")
    else:
        print("No existe tal directorio.")

def main():
    global kill
    global modelo_cargado
    modelo_cargado = "mistral"
    file_path = None
    pregunta = ""
    
    st.title("Chat con PDF usando IA")
    
    #Borrar base de datos
    if "chat" not in st.session_state:
        try:
            lista_carpetas = [
                            '__pycache__',
                            'chroma_db_dir'
                        ]
            for i in lista_carpetas:
                eliminar_contenido_carpeta(i)
            st.session_state.borrar = True
        except:
            st.write("Error desconocido al borrar las carpetas")
            st.session_state.borrar = False
    
    if "borrar" not in st.session_state:
        print("st.session_state.borrar = False")
        st.session_state.borrar = False

    #Subir archivos PDF
    if st.session_state.borrar and "chat" not in st.session_state:
        try:
            uploaded_file = st.file_uploader("Elige un archivo PDF", type="pdf", key='uploaded_file')
            save_folder = "src"
            
            # Crea la carpeta si no existe
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
                
            # Guarda el archivo PDF en la carpeta especificada
            file_path = os.path.join(save_folder, uploaded_file.name)
            st.write("El archivo PDF se ha guardado en:", file_path)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        
            st.session_state.archivos = True
        except FileNotFoundError:
            st.write("No se ha encontrado el archivo PDF a leer")
            st.session_state.archivos = False
        except AttributeError:
            st.session_state.archivos = False
            
    if "archivos" not in st.session_state:
        print("st.session_state.archivos = False")
        st.session_state.archivos = False
        
    #Input
    if ("input" not in st.session_state or st.session_state.input==False) and st.session_state.archivos:
            st.write("Bienvenido al chat con PDF! Escribe 'exit' para cerrar el chat PDF.\n")
            pregunta = st.text_input("User")
            if pregunta!="":
                st.session_state.input=True
            
    if "input" not in st.session_state:
        st.session_state.input = False
        
        st.session_state.cond = "No sé"
        
    #Iniciar chat        
    # if (st.session_state.archivos and st.session_state.borrar) or (file_path is not None and st.session_state.input):
    if ((st.session_state.archivos and st.session_state.borrar) and (file_path is not None and st.session_state.input)) or st.session_state.cond=="cond":
        try:
            if "qa" not in st.session_state:
                kill = False
                qa = iniciar_chat(file_path, modelo_cargado, kill)
                st.session_state.cond = "cond"
                st.session_state.chat = True
                st.session_state.qa = qa
            #Salir de la sesión
            if pregunta.lower() == 'exit':
                st.write("¡Chao!")
                kill = True
                del st.session_state.input 
                del st.session_state.chat
                del st.session_state.qa 
                del st.session_state.archivos 
                iniciar_chat(file_path, modelo_cargado, kill)#Borra base de datos
                st_autorefresh()  # Recarga la aplicación
            else:
                qa = st.session_state.qa
                respuesta = qa.invoke({"query": pregunta})
                metadata = []
                for _ in respuesta['source_documents']:
                    metadata.append(('page: ' + str(_.metadata['page']), _.metadata['file_path']))
                st.write(f"{VERDE}-MISTRAL 7B:{RESET} {respuesta['result']} \n {metadata}")
                st.write("\nRecuerda escribir 'exit' para cerrar el chat PDF\n")
                st.session_state.input = False
        except ollama._types.ResponseError:
                st.write("Carga un modelo que tengas instalado")
                
    #Salir de la sesión con botón
    if st.button("Salir del chat"):
        st.write("¡Chao!")
        kill = True
        del st.session_state.input 
        iniciar_chat(file_path, modelo_cargado, kill) #Borra base de datos
        if "chat" in st.session_state:
            del st.session_state.chat
            del st.session_state.qa 
            del st.session_state.archivos 
            st_autorefresh()  # Recarga la aplicación
                
if __name__ == "__main__":
     main()
