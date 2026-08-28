import uvicorn


if __name__ == "__main__":
    uvicorn.run("marketplace_rooms.order_handoff:app", host="127.0.0.1", port=8000)

