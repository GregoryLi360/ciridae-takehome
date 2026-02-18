import { useState } from "react";
import Header from "@/components/Header";
import Aurora from "@/components/Aurora";
import UploadForm from "@/components/UploadForm";
import JobStatusView from "@/components/JobStatus";
import ResultViewer from "@/components/ResultViewer";
import { useCreateJob, useJobStatus, useJobItems } from "@/api/hooks";
import { MOCK_JOB_COMPLETE, MOCK_ITEMS } from "@/api/mock";

const isDemo = new URLSearchParams(window.location.search).has("demo");

export default function App() {
  const [jobId, setJobId] = useState<string | null>(isDemo ? "demo-001" : null);
  const createJob = useCreateJob();
  const { data: job } = useJobStatus(isDemo ? null : jobId);
  const { data: items } = useJobItems(isDemo ? null : jobId, job?.status === "complete");

  const handleUpload = (files: { jdr: File; insurance: File }) => {
    createJob.mutate(files, {
      onSuccess: (data) => setJobId(data.id),
    });
  };

  const activeJob = isDemo ? MOCK_JOB_COMPLETE : job;
  const activeItems = isDemo ? MOCK_ITEMS : items;
  const isComplete = activeJob?.status === "complete";
  const isProcessing = jobId && activeJob && !isComplete && activeJob.status !== "error";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Aurora />
      <Header />
      <main className="relative z-10 pt-[72px]">
        {!jobId ? (
          <UploadForm
            onSubmit={handleUpload}
            isLoading={createJob.isPending}
            error={createJob.error?.message}
          />
        ) : isProcessing ? (
          <JobStatusView job={activeJob} />
        ) : activeJob ? (
          <ResultViewer job={activeJob} items={activeItems} />
        ) : null}
      </main>
    </div>
  );
}
