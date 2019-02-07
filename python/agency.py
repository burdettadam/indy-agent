import msgpack
import json
import array
import asyncio
import traceback
from indy import wallet, did, error, crypto, pairwise, non_secrets

class Agency:
    def __init__(self):
        self.agency_queue = asyncio.Queue()

    async def start(self):
        self.wallet_handle = await self.setup()
        (self.agency_did, self.agency_vk) = await self.agency_creds()

        print("Agency DID: {}".format(self.agency_did))
        print("Agency VerKey: {}".format(self.agency_vk))

        while True:
            try:
                msg = await self.unpack_vcx_bundle(await self.agency_queue.get())
                print(msg)
            except Exception as e:
                print("\n\n--- Message Processing failed --- \n\n")
                traceback.print_exc()

    async def setup(self):
        try:
            await wallet.create_wallet('{"id": "agency"}', '{"key": "agency"}')
        except error.IndyError as e:
            if e.error_code is error.ErrorCode.WalletAlreadyExistsError:
                pass
            else:
                print("Unexpected Indy Error: {}".format(e))

        try:
            wallet_handle = await wallet.open_wallet('{"id": "agency"}', '{"key": "agency"}')
            return wallet_handle
        except Exception as e:
            print(e)
            print("Could not open wallet!")

        return None

    async def agency_creds(self):
        creds = None
        try:
            creds = json.loads(
                await non_secrets.get_wallet_record(
                    self.wallet_handle,
                    'agency-creds',
                    'agency',
                    '{}'
                )
            )['value']
        except error.IndyError as e:
            if e.error_code is error.ErrorCode.WalletItemNotFound:
                pass
            else:
                raise e

        if not creds:
            print("Creating new did and keys")
            (agency_did, agency_vk) = await did.create_and_store_my_did(self.wallet_handle, '{}')
            # Store agency creds
            creds = json.dumps({
                'did': agency_did,
                'verkey': agency_vk
            })

            await non_secrets.add_wallet_record(
                self.wallet_handle,
                'agency-creds',
                'agency',
                creds,
                '{}'
            )
            return (agency_did, agency_vk)
        else:
            creds = json.loads(creds)
            return (creds['did'], creds['verkey'])

    async def unpack_vcx_bundle(self, bundle):
        wire_msg_bytes = await crypto.anon_decrypt(self.wallet_handle, self.agency_vk, bundle)

        msg = msgpack.unpackb(wire_msg_bytes, raw=False)
        msg = msgpack.unpackb(array.array('B', msg['bundled'][0]).tobytes(), raw=False)
        msg['@msg'] = array.array('B', msg['@msg']).tobytes()
        return msg
