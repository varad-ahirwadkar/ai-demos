import onnx
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python triton_model_config.py <onnx_model_relative_path>")
    sys.exit(1)

model_path = sys.argv[1]

model      = onnx.load(model_path)
model_name = os.path.basename(os.path.dirname(os.path.dirname(model_path)))
config_pbtxt_path = os.path.dirname(os.path.dirname(model_path)) + "/config.pbtxt"

print("model path: %s", model_path)
print("config.pbtxt: %s", config_pbtxt_path)

model_metadata = {
    "name": model_name,
    "platform": "onnxruntime_onnx",
    "max_batch_size": 0,  # change this based on your deployment scenario
    "input": [],
    "output": []
}

# More mapping can be added if required
onnx_data_type_mapping = {
    0: "TYPE_INVALID",
    1: "TYPE_FP32",
    6: "TYPE_INT32",
    7: "TYPE_INT64",
    10: "TYPE_FP16",
    11: "TYPE_FP64"
}

def get_input_dims(input, max_batch_size):
    dims = []
    for dim in input.type.tensor_type.shape.dim:
        if dim.dim_value is not None and dim.dim_value > 0:
            dims.append(dim.dim_value)
        else:
            dims.append(-1)

    # Fix: remove leading -1 if batching is enabled
    if max_batch_size > 0 and len(dims) > 0 and dims[0] == -1:
        dims = dims[1:]

    return dims

for input in model.graph.input:
    input_info = {
        "name": input.name,
        "data_type": onnx_data_type_mapping[input.type.tensor_type.elem_type],
        "dims": get_input_dims(input, model_metadata["max_batch_size"])
    }
    model_metadata["input"].append(input_info)

for output in model.graph.output:
    output_info = {
        "name": output.name,
        "data_type": onnx_data_type_mapping[output.type.tensor_type.elem_type],
        "dims": get_input_dims(output, model_metadata["max_batch_size"])
    }
    model_metadata["output"].append(output_info)

print("model data: \n:", model_metadata)

with open(config_pbtxt_path, "w") as f:
    f.write('name: "{}"\n'.format(model_metadata["name"]))
    f.write('platform: "{}"\n'.format(model_metadata["platform"]))
    f.write("max_batch_size: {}\n".format(model_metadata["max_batch_size"]))

    for input_info in model_metadata["input"]:
        f.write("input {\n")
        f.write('  name: "{}"\n'.format(input_info["name"]))
        f.write("  data_type: {}\n".format(input_info["data_type"]))
        f.write("  dims: [{}]\n".format(", ".join(map(str, input_info["dims"]))))
        f.write("}\n")

    for output_info in model_metadata["output"]:
        f.write("output {\n")
        f.write('  name: "{}"\n'.format(output_info["name"]))
        f.write("  data_type: {}\n".format(output_info["data_type"]))
        f.write("  dims: [{}]\n".format(", ".join(map(str, output_info["dims"]))))
        f.write("}\n")
