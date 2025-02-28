# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os
import unittest
from pathlib import Path

import experiment
import torch
from iopath.common.file_io import PathManager
from omegaconf import OmegaConf
from pytorch3d.implicitron.dataset.json_index_dataset_map_provider import (
    JsonIndexDatasetMapProvider,
)


def interactive_testing_requested() -> bool:
    """
    Certain tests are only useful when run interactively, and so are not regularly run.
    These are activated by this funciton returning True, which the user requests by
    setting the environment variable `PYTORCH3D_INTERACTIVE_TESTING` to 1.
    """
    return os.environ.get("PYTORCH3D_INTERACTIVE_TESTING", "") == "1"


DATA_DIR = Path(__file__).resolve().parent
DEBUG: bool = False

# TODO:
# - sort out path_manager config. Here we monkeypatch to avoid
#    the problem.
# - add enough files to skateboard_first_5 that this works on RE.
# - share common code with PyTorch3D tests?
# - deal with the temporary output files this test creates


def get_path_manager(silence_logs: bool = False) -> PathManager:
    """
    Returns a path manager which can access manifold internally.

    Args:
        silence_logs: Whether to reduce log output from iopath library.
    """
    if silence_logs:
        logging.getLogger("iopath.fb.manifold").setLevel(logging.CRITICAL)
        logging.getLogger("iopath.common.file_io").setLevel(logging.CRITICAL)

    if os.environ.get("INSIDE_RE_WORKER", False):
        raise ValueError("Cannot get to manifold from RE")

    path_manager = PathManager()

    if os.environ.get("FB_TEST", False):
        from iopath.fb.manifold import ManifoldPathHandler

        path_manager.register_handler(ManifoldPathHandler())

    return path_manager


def set_path_manager(self):
    self.path_manager = get_path_manager()


class TestExperiment(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        JsonIndexDatasetMapProvider.__post_init__ = set_path_manager

    def test_from_defaults(self):
        # Test making minimal changes to the dataclass defaults.
        if not interactive_testing_requested():
            return
        cfg = OmegaConf.structured(experiment.ExperimentConfig)
        cfg.data_source_args.dataset_map_provider_class_type = (
            "JsonIndexDatasetMapProvider"
        )
        dataset_args = (
            cfg.data_source_args.dataset_map_provider_JsonIndexDatasetMapProvider_args
        )
        dataloader_args = (
            cfg.data_source_args.data_loader_map_provider_SequenceDataLoaderMapProvider_args
        )
        dataset_args.category = "skateboard"
        dataset_args.test_restrict_sequence_id = 0
        dataset_args.dataset_root = "manifold://co3d/tree/extracted"
        dataset_args.limit_sequences_to = 5
        dataloader_args.dataset_len = 1
        cfg.solver_args.max_epochs = 2

        device = torch.device("cuda:0")
        experiment.run_training(cfg, device)

    def test_yaml_contents(self):
        cfg = OmegaConf.structured(experiment.ExperimentConfig)
        yaml = OmegaConf.to_yaml(cfg, sort_keys=False)
        if DEBUG:
            (DATA_DIR / "experiment.yaml").write_text(yaml)
        self.assertEqual(yaml, (DATA_DIR / "experiment.yaml").read_text())
