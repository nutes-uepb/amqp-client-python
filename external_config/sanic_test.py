from external_config.async_case import config, AsyncEventbusRabbitMQ, rpc_exchange
from sanic import Sanic, response

eventbus = None
app = Sanic("app")
@app.listener("before_server_start")
async def before_server_start(_, loop):
    print("before_server_start")
    global eventbus
    eventbus = AsyncEventbusRabbitMQ(config, loop)
    async def handle(*body):
        print(f"body: {body}")
        await eventbus.rpc_client(rpc_exchange, "user.find2", ["content_message"])
        print("...")
        return b"here"

    async def handle2(*body):
        print(f"body: {body}")
        return b"here"
    await eventbus.provide_resource("user.find", handle)
    await eventbus.provide_resource("user.find2", handle2)



@app.get(uri="/")
async def get(request):
    global eventbus
    result = await eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"])
    return response.json({"message": str(result)})

if __name__ == "__main__":
    app.run()