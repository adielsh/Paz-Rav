"""Connectivity smoke test: connect to the paper gateway, confirm it's a paper account,
print the account summary. No market data — works outside market hours."""
import asyncio
from ib_async import IB

async def main():
    ib = IB()
    await ib.connectAsync("127.0.0.1", 4002, clientId=21, timeout=20)
    print("Connected. server version:", ib.client.serverVersion())
    accts = ib.managedAccounts()
    acct = accts[0] if accts else ""
    print("Managed accounts:", accts, "-> paper?" , acct.startswith("DU"))
    rows = await ib.accountSummaryAsync(acct)
    keys = {"NetLiquidation", "AvailableFunds", "BuyingPower", "InitMarginReq", "MaintMarginReq"}
    for r in rows:
        if r.tag in keys:
            print(f"  {r.tag:16} {r.value} {r.currency}")
    ib.disconnect()
    print("Disconnected. OK.")

asyncio.run(main())
