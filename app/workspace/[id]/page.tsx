"use client";

import React, { Suspense, use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useWallet } from "@/lib/wallet/provider";
import {
  api,
  DatasetItem,
  FindingItem,
  ReportItem,
} from "@/lib/api";
import { DatasetSidebar } from "@/components/dataset-sidebar";
import { Chat } from "@/components/chat";
import { WhyDrawer } from "@/components/why-drawer";
import { DictionaryEditor } from "@/components/dictionary-editor";
import { ReportView } from "@/components/report-view";
import { Loader2 } from "lucide-react";

interface WorkspacePageProps {
  params: Promise<{ id: string }>;
}

function WorkspaceSessionContent({ params }: WorkspacePageProps) {
  const resolvedParams = use(params);
  const sessionId = resolvedParams.id;
  const router = useRouter();
  const { cluster } = useWallet();

  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);

  // Inspector & modal states
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [whyDrawerOpen, setWhyDrawerOpen] = useState(false);
  const [dictionaryDatasetId, setDictionaryDatasetId] = useState<string | null>(null);
  const [activeReport, setActiveReport] = useState<ReportItem | null>(null);

  // Load datasets on mount
  const loadDatasets = async () => {
    try {
      const list = await api.datasets.list();
      setDatasets(list);
      if (list.length > 0 && !activeDatasetId) {
        setActiveDatasetId(list[0].id);
      }
    } catch (err) {
      console.warn("Failed to load datasets:", err);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const handleOpenWhy = (finding: FindingItem) => {
    setSelectedFinding(finding);
    setWhyDrawerOpen(true);
  };

  const handleDatasetAdded = async (datasetId: string) => {
    await loadDatasets();
    setActiveDatasetId(datasetId);
  };

  const handleAttestOnChain = () => {
    if (activeReport) {
      router.push(`/report/${activeReport.id}?attest=true`);
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full overflow-hidden bg-[#090a0f]">
      {/* 1. Left Sidebar: Data Sources */}
      <DatasetSidebar
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        onSelectDataset={setActiveDatasetId}
        onDatasetAdded={handleDatasetAdded}
        onOpenDictionary={(dsId) => setDictionaryDatasetId(dsId)}
      />

      {/* 2. Main Stage: Analysis Chat & Inlined Findings */}
      <main className="flex-1 flex flex-col min-w-0">
        <Chat
          sessionId={sessionId}
          onOpenWhy={handleOpenWhy}
          onReportGenerated={(rep) => setActiveReport(rep)}
        />
      </main>

      {/* 3. Right Drawer: Evidence, Query & Proof Inspector */}
      <WhyDrawer
        finding={selectedFinding}
        isOpen={whyDrawerOpen}
        onClose={() => setWhyDrawerOpen(false)}
        cluster={cluster}
      />

      {/* 4. Data Dictionary Modal */}
      {dictionaryDatasetId && (
        <DictionaryEditor
          datasetId={dictionaryDatasetId}
          isOpen={Boolean(dictionaryDatasetId)}
          onClose={() => setDictionaryDatasetId(null)}
          onSaved={loadDatasets}
        />
      )}

      {/* 5. Report View Modal */}
      {activeReport && (
        <ReportView
          report={activeReport}
          isOpen={Boolean(activeReport)}
          onClose={() => setActiveReport(null)}
          onAttestOnChain={handleAttestOnChain}
        />
      )}
    </div>
  );
}

export default function WorkspaceSessionPage({ params }: WorkspacePageProps) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#090a0f]">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
        </div>
      }
    >
      <WorkspaceSessionContent params={params} />
    </Suspense>
  );
}
