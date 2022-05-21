import os

import torch

from mmlib.constants import CURRENT_DATA_ROOT, MMLIB_CONFIG
from mmlib.deterministic import set_deterministic
from mmlib.equal import model_equal
from mmlib.save import ProvModelListSaveService
from mmlib.save_info import ModelListSaveInfo, ProvListModelSaveInfo, TrainSaveInfo
from mmlib.schema.restorable_object import RestorableObjectWrapper
from mmlib.schema.save_info_builder import ModelSaveInfoBuilder
from mmlib.track_env import track_current_environment
from mmlib.util.dummy_data import imagenet_input
from tests.example_files.battery_data import BatteryData
from tests.example_files.battery_dataloader import BatteryDataloader
from tests.example_files.ffnn_train import FFNNTrainWrapper, FFNNTrainService
from tests.example_files.imagenet_train import ImagenetTrainService, OPTIMIZER, DATALOADER, DATA, ImagenetTrainWrapper
from tests.example_files.mynets.ffnn import FFNN
from tests.save.test_model_list_save_servcie import TestModelListSaveService, dummy_ffnn_input

FILE_PATH = os.path.dirname(os.path.realpath(__file__))
MODEL_PATH = os.path.join(FILE_PATH, '../example_files/mynets/{}.py')
CONFIG = os.path.join(FILE_PATH, '../example_files/local-config.ini')
OPTIMIZER_CODE = os.path.join(FILE_PATH, '../example_files/imagenet_optimizer.py')


class TestProvListSaveService(TestModelListSaveService):

    def setUp(self) -> None:
        super().setUp()
        assert os.path.isfile(CONFIG), \
            'to run these tests define your onw config file named \'local-config\'' \
            'to do so copy the file under tests/example_files/config.ini, and place it in the same directory' \
            'rename it to local-config.ini, create an empty directory and put the path to it in the newly created' \
            'config file, to define the current_data_root'

        os.environ[MMLIB_CONFIG] = CONFIG

    def init_save_service(self, dict_pers_service, file_pers_service):
        self.save_service = ProvModelListSaveService(file_pers_service, dict_pers_service)

    def test_save_restore_provenance_specific_model(self):
        # take three initial models
        initial_model_list = []
        for i in range(3):
            model = FFNN()
            initial_model_list.append(model)

        # save the initial models as full models
        save_info_builder = ModelSaveInfoBuilder()
        env = track_current_environment()
        save_info_builder.add_model_info(model_list=initial_model_list, env=env)
        save_info: ModelListSaveInfo = save_info_builder.build()
        model_list_id = self.save_service.save_models(save_info)

        # recover models and check if they are equal
        restored_model_list_info = self.save_service.recover_models(model_list_id)
        for recovered_model, model in zip(restored_model_list_info.models, initial_model_list):
            self.assertTrue(model_equal(model, recovered_model, dummy_ffnn_input))

        ###################################
        ###################################
        ###################################
        ###################################
        # set deterministic for debugging purposes
        set_deterministic()

        dataset_paths = [
            os.path.abspath(os.path.join(FILE_PATH, '../example_files/data/dummy_battery_data/data_set_1')),
            os.path.abspath(os.path.join(FILE_PATH, '../example_files/data/dummy_battery_data/data_set_2')),
            os.path.abspath(os.path.join(FILE_PATH, '../example_files/data/dummy_battery_data/data_set_3'))
        ]

        ffnn_ts = FFNNTrainService()

        state_dict = {}

        # just start with the first data root
        data_wrapper = BatteryData(root=dataset_paths[0])
        state_dict[DATA] = RestorableObjectWrapper(
            config_args={'root': CURRENT_DATA_ROOT},
            instance=data_wrapper
        )

        data_loader_kwargs = {'batch_size': 16, 'num_workers': 0, 'pin_memory': True}
        dataloader = BatteryDataloader(data_wrapper, **data_loader_kwargs)
        state_dict[DATALOADER] = RestorableObjectWrapper(
            init_args=data_loader_kwargs,
            init_ref_type_args=['dataset'],
            instance=dataloader
        )

        optimizer_kwargs = {'lr': 10 ** -7}
        optimizer = torch.optim.SGD(model.parameters(), **optimizer_kwargs)
        state_dict[OPTIMIZER] = RestorableObjectWrapper(
            import_cmd='from torch.optim import SGD',
            init_args=optimizer_kwargs,
            init_ref_type_args=['params'],
            instance=optimizer
        )

        ffnn_ts.state_objs = state_dict

        _prov_train_service_wrapper = FFNNTrainWrapper(instance=ffnn_ts)

        train_info = TrainSaveInfo(
            train_service_wrapper=_prov_train_service_wrapper,
            train_kwargs={'number_epochs': 10}
        )

        # TODO use builder here
        save_info = ProvListModelSaveInfo()
        save_info.derived_from = model_list_id
        save_info.environment = env
        save_info.dataset_paths = dataset_paths
        save_info.train_info = train_info

        model_id = self.save_service.save_model(save_info)

        ###################################
        ###################################
        ###################################
        ###################################

        # # TODO define model and dataset, generate info per model and corresponding dataset
        # model = initial_model_list[0]
        #
        # ################################################################################################################
        # # as next we define the provenance data, that can not be automatically inferred
        # # All this information has to be only once, for every future version the same prov data can be used
        # # exceptions are the train_kwargs and the raw_data
        # ################################################################################################################
        # # we also have to track the current environment, to store it later
        # prov_env = track_current_environment()
        # # as a last step we have to define the data that should be used and how the train method should be parametrized
        # # TODO think about how to handle training data
        # data_root = os.path.join(FILE_PATH, '../example_files/data/battery_data_root')
        #
        # train_kwargs = {'number_epochs': 10}
        #
        # # to train the model we use the imagenet train service specified above
        # # TODO define own FFNN car battery train service
        # ffnn_ts = ImagenetTrainService()
        # # to make the train service work we have to initialize its state dict containing objects that are required for
        # # training, for example: optimizer and dataloader. The objects in the state dict have to be of type
        # # RestorableObjectWrapper so that the hold instances and their state can be stored and restored
        #
        # # set deterministic for debugging purposes
        # set_deterministic()
        #
        # state_dict = {}
        #
        # # before we can define the data loader, we have to define the data wrapper
        # # for this test case we will use the data from our custom coco dataset
        # data_wrapper = BatteryData(root=data_root)
        # state_dict[DATA] = RestorableObjectWrapper(
        #     config_args={'root': CURRENT_DATA_ROOT},
        #     instance=data_wrapper
        # )
        #
        # # as a dataloader we use the standard implementation provided by pyTorch
        # # this is why we instead of specifying the code path, we specify an import cmd
        # # also we to track all arguments that have been used for initialization of this objects
        # data_loader_kwargs = {'batch_size': 16, 'num_workers': 0, 'pin_memory': True}
        # dataloader = BatteryDataloader(data_wrapper, **data_loader_kwargs)
        # state_dict[DATALOADER] = RestorableObjectWrapper(
        #     init_args=data_loader_kwargs,
        #     init_ref_type_args=['dataset'],
        #     instance=dataloader
        # )
        #
        # # while the other objects do not have an internal state (other than the basic parameters) an optimizer can have
        # # some more extensive state. In pyTorch it offers also the method .state_dict(). To store and restore we use an
        # # Optimizer wrapper object.
        # optimizer_kwargs = {'lr': 10 ** -7}
        # optimizer = torch.optim.SGD(model.parameters(), **optimizer_kwargs)
        # state_dict[OPTIMIZER] = RestorableObjectWrapper(
        #     import_cmd='from torch.utils.data import DataLoader',
        #     init_args=optimizer_kwargs,
        #     init_ref_type_args=['params'],
        #     instance=optimizer
        # )
        #
        # # having created all the objects needed for imagenet training we can plug the state dict into the train servcie
        # ffnn_ts.state_objs = state_dict
        #
        # # finally we wrap the train service in the corresponding wrapper
        # ts_wrapper = ImagenetTrainWrapper(instance=ffnn_ts)
        # ################################################################################################################
        # # having specified all the provenance information that will be used to train a model, we can store it
        # ################################################################################################################
        # save_info_builder = ModelSaveInfoBuilder()
        # save_info_builder.add_model_info(base_model_id=base_model_id, env=prov_env)
        # save_info_builder.add_prov_data(
        #     raw_data_path=raw_data, train_kwargs=train_kwargs, train_service_wrapper=ts_wrapper)
        # save_info = save_info_builder.build()
        #
        # ################################################################################################################
        # # restoring this model will result in a model that was trained according to the given provenance data
        # # in this case it should be equivalent to the initial model trained using the specified train_service using the
        # # specified data and train kwargs
        # ################################################################################################################
        # model_id = self.save_service.save_model(save_info)
        #
        # ffnn_ts.train(model, **train_kwargs)
        # self.save_service.add_weights_hash_info(model_id, model)
        # recovered_model_info = self.save_service.recover_model(model_id, execute_checks=True)
        # recovered_model_1 = recovered_model_info.model
        #
        # ################################################################################################################
        # # Having defined the provenance information above storing a second version is a lot shorter
        # ################################################################################################################
        # save_info_builder = ModelSaveInfoBuilder()
        # save_info_builder.add_model_info(base_model_id=model_id, env=prov_env)
        # save_info_builder.add_prov_data(raw_data_path=raw_data, train_kwargs=train_kwargs,
        #                                 train_service_wrapper=ts_wrapper)
        # save_info = save_info_builder.build()
        #
        # model_id_2 = self.save_service.save_model(save_info)
        #
        # ffnn_ts.train(model, **train_kwargs)
        # self.save_service.add_weights_hash_info(model_id_2, model)
        #
        # recovered_model_info = self.save_service.recover_model(model_id_2, execute_checks=True)
        # self.assertTrue(model_equal(model, recovered_model_info.model, imagenet_input))
        # self.assertFalse(model_equal(recovered_model_1, recovered_model_info.model, imagenet_input))
