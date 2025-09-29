import onnx
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python extract_model.py <onnx_model_relative_path>")
    sys.exit(1)

model_path = sys.argv[1]

#model_path = "data-drift-model/gaussian-credit-model/1/model.onnx"
model      = onnx.load(model_path)
model_name = os.path.basename(os.path.dirname(os.path.dirname(model_path)))
config_pbtxt_path = os.path.dirname(os.path.dirname(model_path)) + "/config.pbtxt"

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

for input in model.graph.input:
    input_info = {
        "name": input.name,
        "data_type": onnx_data_type_mapping[input.type.tensor_type.elem_type],
        "dims": [dim.dim_value if (dim.dim_value is not None and dim.dim_value>0) else -1 for dim in input.type.tensor_type.shape.dim]
    }
    model_metadata["input"].append(input_info)

for output in model.graph.output:
    output_info = {
        "name": output.name,
        "data_type": onnx_data_type_mapping[output.type.tensor_type.elem_type],
        "dims": [dim.dim_value if (dim.dim_value is not None and dim.dim_value>0) else -1 for dim in output.type.tensor_type.shape.dim]
    }
    model_metadata["output"].append(output_info)


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
