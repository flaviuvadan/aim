import uuid
from copy import deepcopy
import grpc
import aim.ext.transport.remote_tracking_pb2 as rpc_messages
import aim.ext.transport.remote_tracking_pb2_grpc as remote_tracking_pb2_grpc

from aim.ext.transport.message_utils import pack, unpack, unpack_response_data
from aim.storage.treeutils import encode_tree, decode_tree


class Client:
    def __init__(self, remote_path: str):
        self._id = str(uuid.uuid4())
        self._remote_channel = grpc.insecure_channel(remote_path)
        self._remote_stub = remote_tracking_pb2_grpc.RemoteTrackingServiceStub(self._remote_channel)

    def get_resource_handler(self, resource_type, args=()):
        request = rpc_messages.ResourceRequest(
            resource_type=resource_type,
            client_uri=self.uri,
            args=args
        )
        response = self._remote_stub.get_resource(request)
        if response.status == rpc_messages.ResourceResponse.Status.OK:
            return response.handler
        return None

    def run_instruction_no_stream(self, resource, method, args):
        message = pack(encode_tree(args))
        resp = self._remote_stub.run_instruction_no_stream(rpc_messages.InstructionRequestNoStream(
            header=rpc_messages.RequestHeader(
                version='0.1',
                handler=resource,
                client_uri=self.uri,
                method_name=method
            ),
            message=message
        ))
        return InstructionResponseViewNoFetch(resp)

    def run_instruction(self, resource, method, args):
        args = deepcopy(args)

        def message_stream_generator():
            header = rpc_messages.InstructionRequest(
                header=rpc_messages.RequestHeader(
                    version='0.1',
                    handler=resource,
                    client_uri=self.uri,
                    method_name=method
                )
            )
            yield header

            stream = pack(encode_tree(args))
            for chunk in stream:
                yield rpc_messages.InstructionRequest(message=chunk)

        resp = self._remote_stub.run_instruction(message_stream_generator())
        status_msg = next(resp)
        assert status_msg.WhichOneof('instruction') == 'header'
        if status_msg.header.status != rpc_messages.ResponseHeader.Status.OK:
            raise RuntimeError('something went wrong')
        return decode_tree(unpack_response_data(resp))

    @property
    def remote(self):  # access to low-level interface
        return self._remote_stub

    @property
    def uri(self):
        return self._id
