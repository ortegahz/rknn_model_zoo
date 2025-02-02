import copy
import os
from ruamel import yaml
from collections import OrderedDict

# devices_type
NPU_VERSION_1_DEVICES = ['RK3399PRO', 'RK1808', 'RV1109', 'RV1126']
NPU_VERSION_2_DEVICES = ['RK3566', 'RK3568', 'RK3588', 'RV1106', 'RV1103']

QUANTIZE_DTYPE_MAP = {
    'asymmetric_affine-u8': 'u8',
    'dynamic_fixed_point-i8': 'i8', 
    'dynamic_fixed_point-i16': 'i16',
    'asymmetric_quantized-8': 'i8',             # For NPU-2: asymmetric_quantized-8
}


def _dict_to_str(tar_dict):
    _ignore_key = ['img_size']
    _supress_key = ['input_example']
    _supress_lenth = 100
    def _parse_dict(_d, _srt_list, _depth=0):
        _blank = ' '*2
        for _key, _value in _d.items():
            # ignore some key
            if _key in _ignore_key:
                continue

            if isinstance(_value, dict):
                _str.append(_blank*_depth + _key + ':')
                _parse_dict(_value, _srt_list, _depth+1)
            elif _value is None:
                continue
            else:
                _srt_list.append(_blank*_depth + _key + ': ' + str(_value))
                if _key in _supress_key:
                    _srt_list[-1] = _srt_list[-1][:_supress_lenth] + '  ...'

    if not isinstance(tar_dict, dict):
        print('{} is not a dict'.format(tar_dict))

    _str = []
    _parse_dict(tar_dict, _str)
    return _str


def get_example_img_from_dataset(dataset_path, quantize_status):
    with open(dataset_path, 'r') as f:
        contents = f.readlines()
    examples = []
    dataset_dir = os.path.dirname(dataset_path)

    for _path in contents:
        _path = _path.rstrip('\n')
        inputs_list = _path.split(' ')

        # check exist
        for i in range(len(inputs_list)):
            _path = copy.deepcopy(inputs_list[i])
            if not os.path.isabs(_path):
                _path = os.path.join(dataset_dir, _path)
                inputs_list[i] = _path
            if not os.path.exists(_path):
                if quantize_status is True:
                    assert False, '|| {} || input path in dataset.txt not exist'.format(_path)
                elif quantize_status is False:
                    print("|| {} || input path in dataset.txt not exist, compute convert loss will be failed".format(_path))
                    continue
        examples.append(inputs_list)
    return examples


class RKNN_config_container:
    def __init__(self, config) -> None:
        if isinstance(config, str):
            self.yml_file_path = config
            with open(config, 'r') as f:
                # project_config = yaml.load(f)
                project_config = yaml.safe_load(f)
        else:
            project_config = copy.deepcopy(config)

        self.project_config = project_config
        self.RK_device_platform = project_config.get('RK_device_platform', 'RK1808').upper()

    def parse_hyper_config(self):
        # config not exists in rknn_api
        RK_device_platform = self.RK_device_platform
        if RK_device_platform in NPU_VERSION_1_DEVICES:
            self.NPU_VERSION = 1
        elif RK_device_platform in NPU_VERSION_2_DEVICES:
            self.NPU_VERSION = 2
        else:
            assert False, "{} devices is not support. Now support devices list - {}".format(RK_device_platform, NPU_VERSION_2_DEVICES+ NPU_VERSION_1_DEVICES)
        self.RK_device_platform = RK_device_platform

        self.convert_config_dict = {}
        self.convert_config_dict['NPU_VERSION'] = self.NPU_VERSION
        self.convert_config_dict['RK_device_platform'] = RK_device_platform
        self.convert_config_dict['input_example'] = self.project_config.get('input_example', None)
        self.convert_config_dict['pre_compile'] = self.project_config.get('pre_compile', 'off')
        
        self.convert_config_dict['core_mask'] = self.project_config.get('core_mask', 1)       # For rk3588, defualt first core.
        # 1 = 0,0,1
        # 2 = 0,1,0
        # 3 = 0,1,1
        # 4 = 1,0,0
        # 7 = 1,1,1

    def init_rknn_config(self):
        # defualt config
        rknn_config = {}
        rknn_config['target_platform'] = self.RK_device_platform
        rknn_config['quantized_dtype'] = 'asymmetric_affine-u8' # For NPU-1: asymmetric_affine-u8, dynamic_fixed_point-i8, dynamic_fixed_point-i16
                                                                # For NPU-2: asymmetric_quantized-8
        rknn_config['quantized_algorithm'] = 'normal'           # For NPU-1: normal(default), mmse, kl_divergence, moving_average
                                                                # For NPU-2: normal(default), mmse
        rknn_config['optimization_level'] = 3
        rknn_config['mean_values'] = None
        rknn_config['std_values'] = None

        if self.NPU_VERSION == 1:
            rknn_config['mmse_epoch'] = 3
            rknn_config['do_sparse_network'] = True
            rknn_config['output_optimize'] = 0
            rknn_config['batch_size'] = 100

            rknn_config['quantize_input_node'] = False
            rknn_config['inputs_scale_range'] = None
            rknn_config['merge_dequant_layer_and_output_node'] = False

            rknn_config['force_builtin_perm'] = False
            # rknn_config['using_conv_as_preprocess'] = None

        elif self.NPU_VERSION == 2:
            rknn_config['quantized_method'] = 'channel'
            rknn_config['custom_string'] = None
            # rknn_config['output_tensor_type'] = None

        self.convert_config_dict['config'] = rknn_config

    def init_export_config(self):
        export_rknn_config = {}
        export_rknn_config['export_path'] = None
        self.convert_config_dict['export_rknn'] = export_rknn_config

    def parse_rknn_object_config(self):
        self.convert_config_dict['verbose'] = self.project_config.get('verbose', False)
        self.convert_config_dict['verbose_file'] = self.project_config.get('verbose_file', None)

    def parse_init_runtime_config(self):
        self.convert_config_dict['RK_device_id'] = self.project_config.get('RK_device_id', None)
        if not isinstance(self.convert_config_dict['RK_device_id'], str) and \
            self.convert_config_dict['RK_device_id'] is not None:
            self.convert_config_dict['RK_device_id'] = str(self.convert_config_dict['RK_device_id'])

    def parse_build_config(self):
        if hasattr(self, 'yml_file_path'):
            model_path_dir = os.path.dirname(self.yml_file_path)
        else:
            model_path_dir = ''
        self.convert_config_dict['dataset'] = self.project_config.get('dataset', None)
        if self.convert_config_dict['dataset'] is not None:
            self.convert_config_dict['dataset'] = os.path.join(model_path_dir, self.convert_config_dict['dataset'])
        self.convert_config_dict['quantize'] = self.project_config.get('quantize', False)

        build_config = {}
        build_config['do_quantization'] = self.convert_config_dict['quantize']
        build_config['dataset'] = self.convert_config_dict['dataset']
        self.convert_config_dict['build'] = build_config

    def parse_model_load_config(self):
        if hasattr(self, 'yml_file_path'):
            model_path_dir = os.path.dirname(self.yml_file_path)
        else:
            model_path_dir = ''
        project_config = self.project_config
        model_framework = project_config.get('model_framework', None)
        assert model_framework != None, 'platform shoule be define in config_file'
        self.convert_config_dict['model_framework'] = model_framework
        model_load_dict = {}
        if 'model_file_path' in project_config:
            # for onnx/pytorch/tensorflow/tflite/keras
            model_load_dict['model'] = os.path.join(model_path_dir, project_config['model_file_path'])
            if model_framework == 'pytorch':
                self.convert_config_dict['qnnpack'] = project_config.get('qnnpack','False')

        if model_framework == 'caffe':
            model_load_dict['model'] = os.path.join(model_path_dir, project_config['prototxt_file_path'])
            model_load_dict['blobs'] = os.path.join(model_path_dir, project_config['caffemodel_file_path'])
            if self.NPU_VERSION == 1:
                model_load_dict['proto'] = 'caffe'
        elif model_framework == 'darknet':
            model_load_dict['model'] = os.path.join(model_path_dir, project_config['cfg_file_path'])
            model_load_dict['weight'] = os.path.join(model_path_dir, project_config['weight_file_path'])
        elif model_framework == 'mxnet':
            model_load_dict['symbol'] = os.path.join(model_path_dir, project_config['json_file_path'])
            model_load_dict['params'] = os.path.join(model_path_dir, project_config['params_file_path'])
        elif model_framework == 'tensorflow':
            model_load_dict.pop('model')
            model_load_dict['tf_pb'] = os.path.join(model_path_dir, project_config['model_file_path'])

        self.convert_config_dict['load'] = model_load_dict

    def parse_graph(self):
        project_config = self.project_config
        graph = project_config.get('graph', None)
        assert graph != None, "graph should be define in config file"

        # graph input
        inputs_info = OrderedDict()
        if 'in' in graph:
            assert ('in_0' in graph)^('in' in graph), "if graph has multi in, use in_0, in_1 etc."
            inputs_info['in'] = graph['in']
        else:
            start_index = 0
            while True:
                _name = 'in_{}'.format(start_index)
                if _name in graph:
                    inputs_info[_name] = graph[_name]
                    start_index+=1
                else:
                    break
        self.convert_config_dict['inputs'] = inputs_info

        # graph output
        outputs_info = OrderedDict()
        if 'out' in graph:
            assert ('out_0' in graph)^('out' in graph), "if graph has multi out, use out_0, out_1 etc."
            outputs_info['out'] = graph['out']
        else:
            start_index = 0
            while True:
                _name = 'out_{}'.format(start_index)
                if _name in graph:
                    outputs_info[_name] = graph[_name]
                    start_index+=1
                else:
                    break
        self.convert_config_dict['outputs'] = outputs_info

    def update_config(self):
        if 'configs' in self.project_config:
            rknn_configs_dict = copy.deepcopy(self.convert_config_dict['config'])
            specific_config = self.project_config['configs']

            # some valid we do not recommand to use, reject it.
            _key_list = list(specific_config.keys())
            for key in _key_list:
                if key not in rknn_configs_dict:
                    print("{} is not a valid param for {}(RKNN_toolkit{})".format(key, self.RK_device_platform, self.NPU_VERSION))
                    specific_config.pop(key)
            # update dict
            rknn_configs_dict.update(specific_config)
            self.convert_config_dict['config'] = rknn_configs_dict


    def update_dataset(self):
        inputs_example = self.convert_config_dict.get('input_example', None)
        if inputs_example is None:
            if self.convert_config_dict['dataset'] is not None:
                multi_examples = get_example_img_from_dataset(self.convert_config_dict['dataset'], self.convert_config_dict['build']['do_quantization'])
            else:
                return 
        else:
            multi_examples = inputs_example.split(' ')
        
        inputs_path_list_with_port = []
        inputs_key = list(self.convert_config_dict['inputs'].keys())
        for single_example in multi_examples:
            _temp_dict = {}
            for i in range(len(inputs_key)):
                _temp_dict[inputs_key[i]] = single_example[i]
            inputs_path_list_with_port.append(_temp_dict)

        self.convert_config_dict['input_example'] = inputs_path_list_with_port

        # hybrid
    '''
    def update_pre_compile(self):
        #! No more support offline precompile
        # if self.convert_config_dict['pre_compile'] == 'offline':
        #     self.convert_config_dict['build']['pre_compile'] = True
        pass
    '''

    '''
    def update_img_example(self):
        if (self.convert_config_dict['img_example'] == None) and (self.convert_config_dict['compute_convert_cosine_loss'] ==True):
            # TODO add dataset.txt fisrt img
            pass
    '''

    def update_graph(self):
        self.project_config['no_scale_values'] = True

        mean_values_list = []
        std_values_list = []
        input_size_list = []
        reorder_list = []       # For toolkit1
        channel_type_list = []  # For toolkit2
        inputs_name = []
        outputs_name = []

        graph_update_dict = {}

        for key, sub_dict in self.convert_config_dict['inputs'].items():
            assert 'shape' in sub_dict, "shape must be define for {}".format(key)
            # record node name if available
            _input_name = sub_dict.get('name', None)
            if _input_name is not None:
                inputs_name.append(_input_name)

            # input_size_list
            input_size_list.append([int(_v) for _v in str(sub_dict['shape']).split(',')])
            if self.convert_config_dict['model_framework'] in ['tensorflow', 'tflite', 'keras']:
                if len(input_size_list[-1]) == 1:
                    channel_dim_size = 1
                else:
                    channel_dim_size = input_size_list[-1][-1]
                img_size = input_size_list[-1][0:-1]
            else:
                if len(input_size_list[-1]) == 1:
                    channel_dim_size = 1
                else:
                    channel_dim_size = input_size_list[-1][0]
                img_size = input_size_list[-1][1:]
            
            # mean_values
            mean_values = sub_dict.get('mean_values', 0)
            if mean_values!= 0:
                self.project_config['no_scale_values'] = False
            if isinstance(mean_values, str):
                mean_values_list.append([float(_v) for _v in mean_values.split(',')])
            else:
                mean_values_list.append([mean_values]* channel_dim_size)

            # std_values
            std_values = sub_dict.get('std_values', 1)
            if std_values!= 1:
                self.project_config['no_scale_values'] = False
            if isinstance(std_values, str):
                std_values_list.append([float(_v) for _v in std_values.split(',')])
            else:
                std_values_list.append([std_values]* channel_dim_size)

            # reorder_channel
            channel_type = sub_dict.get('img_type', None)
            if channel_type is None:
                #! not allow some input with img_type and other without img_type
                if len(input_size_list[-1]) == 2 or \
                    (len(input_size_list[-1]) ==3 and input_size_list[-1][0] == 1):
                    channel_type = 'GRAY' 
                channel_type_list = False
                # channel_type = 'RGB'
            else:
                if channel_type == 'BGR':
                    channel_type_list.append(True)
                    reorder_list.append('2 1 0')
                elif channel_type == 'RGB':
                    channel_type_list.append(False)
                    reorder_list.append('0 1 2')
                else:
                    assert False, "only RGB or BGR support, got img_type-{}".format(channel_type)

            # update convert_config_dict['inputs'] dict
            _input_update_dict = {}
            _input_update_dict['shape'] = input_size_list[-1]
            _input_update_dict['mean_values'] = mean_values_list[-1]
            _input_update_dict['std_values'] = std_values_list[-1]
            _input_update_dict['img_type'] = channel_type
            _input_update_dict['img_size'] = img_size
            graph_update_dict[key] = _input_update_dict

        self.convert_config_dict['inputs'] = graph_update_dict

        for key, sub_dict in self.convert_config_dict['outputs'].items():
            outputs_name.append(sub_dict['name'])
            
        # update to real position
        self.convert_config_dict['config']['mean_values'] = mean_values_list
        self.convert_config_dict['config']['std_values'] = std_values_list
        if self.NPU_VERSION == 1:
            if len(reorder_list) == 0:
                self.convert_config_dict['config']['reorder_channel'] = None
            else:
                self.convert_config_dict['config']['reorder_channel'] = '#'.join(reorder_list)
        elif self.NPU_VERSION == 2:
            self.convert_config_dict['config']['quant_img_RGB2BGR'] = channel_type_list

        # TODO if other model_framework support load subgraph, add here 
        if self.convert_config_dict['model_framework'] in ['tensorflow', 'onnx'] and \
            inputs_name != [] and outputs_name != []:
            pass
            # TODO support
            self.convert_config_dict['load']['inputs'] = inputs_name
            self.convert_config_dict['load']['outputs'] = outputs_name

        # model_framework need input size
        if self.convert_config_dict['model_framework'] in ['pytorch', 'tensorflow', 'mxnet']:
            if self.NPU_VERSION == 1:
                self.convert_config_dict['load']['input_size_list'] = input_size_list
            elif self.NPU_VERSION == 2:
                _input_size_list = [[1,*_size] for _size in input_size_list]
                self.convert_config_dict['load']['input_size_list'] = _input_size_list

    def update_path(self, path_type, given_path):
        model_name = self.project_config.get('model_name', None)
        merge_platform = {
            'RK1808': 'RK1808_3399pro',
            'RK3399PRO': 'RK1808_3399pro',
            'RV1126': 'RV1109_1126',
            'RV1109': 'RV1109_1126',
            'RV1103': 'RV1103_1106',
            'RV1106': 'RV1103_1106',
            'RK3566': 'RK356X',
            'RK3568': 'RK356X',
            'RK3588': 'RK3588',
        }
        platform = merge_platform[self.project_config['RK_device_platform'].upper()]
        
        if model_name is None:
            model_name = 'model'
            src_model_name = self.convert_config_dict['load'].get('model', None)
            if src_model_name is not None:
                src_model_name = src_model_name.split(os.sep)[-1]
                model_name = '.'.join(src_model_name.split('.')[0:-1])

        dtype = QUANTIZE_DTYPE_MAP[self.convert_config_dict['config']['quantized_dtype']] if self.project_config['quantize'] else 'fp'
        model_name = '_'.join([model_name, 
                               platform,
                               dtype,
                              ])

        sub_folder = './model_cvt'
        if given_path == 'AUTO':
            _ = os.mkdir(sub_folder) if os.path.exists(sub_folder) is not True else 0
            device_folder = os.path.join(sub_folder, platform)
            _ = os.mkdir(device_folder) if os.path.exists(device_folder) is not True else 0
            given_path = os.path.join(device_folder, model_name)
        elif not given_path.endswith('.rknn'):
            given_path = os.path.join(given_path, model_name)

        self.convert_config_dict['export_rknn']['export_path'] = given_path.rstrip('.rknn') + '.rknn'
        self.convert_config_dict['export_pre_compile_path'] = given_path.rstrip('.rknn') + '_precompile.rknn'

    '''
    def set_quantize(self, quantize):
        # None mean using quantize param in config file
        # False mean disable quantize
        # True mean enable quantize 
        if quantize is not None:
            if quantize == 'False':
                quantize = False
            elif quantize == 'True':
                quantize = True
            self.convert_config_dict['build']['do_quantization'] = quantize
    '''

    def print_config(self):
        # TODO optimize print logic
        print('='*10, 'parser_config', '='*10)
        _str = _dict_to_str(self.convert_config_dict)
        for _s in _str:
            print(_s)
        print('='*35)

    def align_quantized_type(self):
        if self.NPU_VERSION == 1 and \
           self.convert_config_dict['config']['quantized_dtype'] == 'asymmetric_quantized-8':
            self.convert_config_dict['config']['quantized_dtype'] = 'asymmetric_affine-u8'
        elif self.NPU_VERSION == 2 and \
             self.convert_config_dict['config']['quantized_dtype'] == 'asymmetric_affine-u8':
             self.convert_config_dict['config']['quantized_dtype'] = 'asymmetric_quantized-8'

    def remove_mean_std_if_neednt(self):
        if self.project_config.get('no_scale_values', False):
            self.convert_config_dict['config'].pop('mean_values')
            self.convert_config_dict['config'].pop('std_values')
            for key, info in self.convert_config_dict['inputs'].items():
                info.pop('mean_values')
                info.pop('std_values')

    def push_back(self):
        return self.convert_config_dict

    def parse(self):
        self.parse_hyper_config()
        self.init_rknn_config()
        self.init_export_config()

        self.parse_rknn_object_config()
        self.parse_build_config()
        self.parse_model_load_config()
        self.parse_graph()
        self.parse_init_runtime_config()

        self.update_graph()
        self.update_config()
        self.update_dataset()
        self.align_quantized_type()     # align toolkit1,toolkit2 format
        self.remove_mean_std_if_neednt()

