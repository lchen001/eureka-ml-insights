import os
from typing import Any, Optional

from eureka_ml_insights.core import (
    DataProcessing,
    Inference,
    PromptProcessing,
)
from eureka_ml_insights.core.eval_reporting import EvalReporting
from eureka_ml_insights.data_utils import (
    AddColumn,
    ColumnRename,
    DataReader,
    HFDataReader,
    MMDataLoader,
    SequenceTransform,
    SamplerTransform,
    
)


from eureka_ml_insights.data_utils.aime_utils import (
    AIMEExtractAnswer
)



from eureka_ml_insights.data_utils.data import (
    DataLoader,
    DataReader,
    HFDataReader,
)
from eureka_ml_insights.data_utils.transform import RunPythonTransform, ColumnRename
from eureka_ml_insights.metrics.aime_metrics import AIME_ExactMatch

from eureka_ml_insights.metrics.reports import (
    AverageAggregator,
    TwoColumnSumAverageAggregator,
)

from .config import (
    AggregatorConfig,
    DataProcessingConfig,
    DataSetConfig,
    EvalReportingConfig,
    InferenceConfig,
    MetricConfig,
    ModelConfig,
    PipelineConfig,
    PromptProcessingConfig,
)
from .experiment_config import ExperimentConfig


class AIME_PIPELINE(ExperimentConfig):
    """This class specifies the config for running IFEval benchmark on any model"""

    def configure_pipeline(
        self, model_config: ModelConfig, resume_from: str = None, 
        **kwargs: dict[str, Any]) -> PipelineConfig:

        # data preprocessing
        self.data_processing_comp = PromptProcessingConfig(
            component_type=PromptProcessing,
            data_reader_config=DataSetConfig(
                HFDataReader,
                {
                    "path": "qq8933/AIME_1983_2024",
                    "split": "train",
                    
                    "transform": SequenceTransform(
                    [
                        ColumnRename(
                                name_mapping={
                                    "Question": "prompt",
                                    "Answer": "ground_truth",

                                    }
                            ),
                        RunPythonTransform("df = df[df['Year']==2024]")
                    
                    ],
                    ),
                    
                },
            ),
            
            prompt_template_path=os.path.join(
                os.path.dirname(__file__), "../prompt_templates/aime_templates/Template_1a.jinja"
            ),            
            output_dir=os.path.join(self.log_dir, "data_processing_output"),
        )

        # inference component
        self.inference_comp = InferenceConfig(
            component_type=Inference,
            model_config=model_config,
            data_loader_config=DataSetConfig(
                DataLoader,
                {"path": os.path.join(self.data_processing_comp.output_dir, "transformed_data.jsonl")},
            ),
            output_dir=os.path.join(self.log_dir, "inference_result"),
            resume_from=resume_from,
        )
        # post process the response to extract the answer
        self.data_post_processing = DataProcessingConfig(
            component_type=DataProcessing,
            data_reader_config=DataSetConfig(
                DataReader,
                {
                    "path": os.path.join(self.inference_comp.output_dir, "inference_result.jsonl"),
                    "format": ".jsonl",
                    "transform": SequenceTransform(
                        [ColumnRename({"model_output": "model_response"}), AIMEExtractAnswer("model_response", "model_output")]
                    ),
                },
            ),
            output_dir=os.path.join(self.log_dir, "data_post_processing_output"),
        )
        
        # Configure the evaluation and reporting component for evaluation and dataset level aggregation        
        self.evalreporting_comp = EvalReportingConfig(
            component_type=EvalReporting,
            data_reader_config=DataSetConfig(
                DataReader,
                {
                    "path": os.path.join(self.data_post_processing.output_dir, "transformed_data.jsonl"),
                    "format": ".jsonl",
                },
            ),
            metric_config=MetricConfig(
                AIME_ExactMatch
            ),
            aggregator_configs=[
                AggregatorConfig(
                    AverageAggregator,
                    {
                        "column_names": [
                            "AIME_ExactMatch_result",
                        ],
                        "group_by": "Year",
                        "filename_base": "ExactMatch_GroupBy",
                    },
                ),
            ],
            output_dir=os.path.join(self.log_dir, "eval_report"),
        )

        # Configure the pipeline
        return PipelineConfig(
            [
                self.data_processing_comp,
                self.inference_comp,
                self.data_post_processing,
                self.evalreporting_comp,
            ],
            self.log_dir,
        )
