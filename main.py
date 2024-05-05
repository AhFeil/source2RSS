import uvicorn

from source2rss import app




if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=7500)

    # uvicorn main:app --host 0.0.0.0 --port 7500



    
    
