from typing import List, Callable, Optional, Tuple

import numpy as np
from rich.console import Console
from rich.table import Table
# from tqdm.notebook import tqdm
from tqdm import tqdm

from ..core import BaseModel
from ...datasets import Dataset
from ...typing import ArrayLike


# todo: handle tailing instances (merged to former?)
class ActiveLearningPipeline:
    # list/dict/obj are settable
    _params = ["model", "stats", "seeds", "current_stat"]

    def __init__(
        self,
        model: BaseModel,
        dataset: Dataset,
        eval_metrics: List[Callable],
        model_maker: Optional[Callable] = None,
        eval_set: Optional[Tuple[ArrayLike, ArrayLike]] = None,
        batch_size_updater: Optional[Callable] = None,
        n_times: int = 1,
        verbose: bool = True,
        seeds: List[int] = None,
        early_stop: int = 20,
        *args,
        **kwargs
    ):
        """ Initialize the pipeline

        Args:
            model: the target model
            dataset: dataset of class `Dataset`, feed data with al metric
            eval_metrics: evaluating metrics for prediction. can be generated by `get_metrics`
            eval_set: optional. use test set provided by `dataset` if not provided
            batch_size_updater: callable function that updates the batch size during training
            n_times: times to run the pipeline
            verbose: print logs / draw progress for each run
            seeds: random seed list for each run
        """
        self.verbose = verbose
        self.n_times = n_times
        self.early_stop = early_stop
        self.model_maker = model_maker
        self.seeds = seeds if seeds is not None else np.random.randint(low=0, high=n_times * 10, size=(n_times, ))
        if len(self.seeds) != n_times:
            raise RuntimeError("seed number does not consists with n times")

        self.batch_size_updater = batch_size_updater
        self._model = model
        if len(eval_metrics) == 0:
            print("[WARNING] Start without evaluating metrics")
            # raise RuntimeError("Require at least one valid evaluating metrics")
        self.dataset = dataset
        self.__eval_metrics = eval_metrics
        # if not specify the test set then use test set from `self.dataset`
        self.__eval_set = eval_set or (self.dataset.test_x, self.dataset.test_y)
        # init stats
        self.current_stat = {}
        self.stats = []
        self.__new_stat()
        self.dataset.bind_params(self.params)

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value
        self.dataset.bind_params(self.params)

    def __new_stat(self):
        if self.current_stat:
            self.stats.append(self.current_stat)
        self.current_stat = {mc.__name__: [] for mc in self.__eval_metrics} | {
            "seed": -1,
            "instances": [],
            "snapshot": [],
            "model_snapshots": [],
            "predictions": [],
            "prob": [],
            "fi":[]
        }

    @property
    def params(self):
        return {k: object.__getattribute__(self, k) for k in self._params}

    def apply_eval_metrics(self):
        # update instance amount
        self.current_stat["instances"].append(self.dataset.l_size)
        self.current_stat["predictions"].append(
            self.model.predict(self.dataset.test_x)
        )
        self.current_stat["prob"].append(
            self.model.predict_proba(self.dataset.test_x)
        )
        for mc in self.__eval_metrics:
            # pred = self.model.predict(self.__eval_set[0])
            self.current_stat[mc.__name__].append(
                mc(
                    estimator=self.model,
                    X=self.dataset.test_x,
                    y_true=self.dataset.test_y,
                )
            )

    def print_score(self, rich: bool = True):
        if not self.verbose:
            return
        if not rich:
            print(self.current_stat)
            return
        table = Table(title="Score")
        table.add_column("Metric", justify="right", style="bold cyan", no_wrap=True)
        table.add_column("Latest Value", style="green")
        for k, v in self.current_stat.items():
            table.add_row(k, str(v[-1]))
        console = Console()
        console.print(table)

    def epoch(self):
        """ [OVERRIDE NEEDED] Run one epoch """
        pass

    def before_run(self, n_iter: Optional[int] = None):
        """ [OVERRIDE NEEDED] Exec before each run """
        # init random state of dataset
        self.dataset.bind_params(self.params)
        self.dataset.update_iteration(n_iter)
        self.current_stat["seed"] = self.seeds[n_iter]

    def after_run(self, n_iter: Optional[int] = None):
        self.dataset.bind_params(self.params)
        self.dataset.update_iteration(n_iter)

    def run(self, n_iter: Optional[int] = None):
        """ [OVERRIDE NEEDED] Run whole pipeline once """
        # ...
        # self.apply_eval_metrics()
        # self.print_score()
        # self.__new_stat()
        pass

    def start(self):
        """ [OVERRIDE NEEDED] Run the pipeline n times """
        prog = tqdm(range(self.n_times)) if self.verbose else range(self.n_times)
        for i in prog:
            self.before_run(n_iter=i)
            self.run(n_iter=i)
            self.after_run(n_iter=i)
            # self.apply_eval_metrics()
            # self.print_score()
            self.__new_stat()
            # self.dataset.reset()
