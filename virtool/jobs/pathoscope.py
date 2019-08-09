"""
Functions and job classes for sample analysis.

"""
import json
import os
import shlex

import pymongo
import pymongo.errors

import virtool.db.caches
import virtool.db.sync
import virtool.jobs.analysis
import virtool.jobs.job
import virtool.jobs.utils
import virtool.otus
import virtool.pathoscope
import virtool.samples
import virtool.db.samples

TRIMMING_PROGRAM = "skewer-0.2.2"


class Job(virtool.jobs.analysis.Job):
    """
    A base class for all analysis job objects. Functions include:

    - establishing synchronous database connection
    - extracting task args to attributes
    - retrieving the sample and host documents
    - calculating the sample read count
    - constructing paths used by all subclasses

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._stage_list = [
            self.make_analysis_dir,
            self.prepare_reads,
            self.prepare_qc,
            self.map_default_isolates,
            self.generate_isolate_fasta,
            self.build_isolate_index,
            self.map_isolates,
            self.map_subtraction,
            self.subtract_mapping,
            self.pathoscope,
            self.import_results,
            self.cleanup_indexes
        ]

    def map_default_isolates(self):
        """
        Using ``bowtie2``, maps reads to the main otu reference. This mapping is used to identify candidate otus.

        """
        command = [
            "bowtie2",
            "-p", str(self.proc),
            "--no-unal",
            "--local",
            "--score-min", "L,20,1.0",
            "-N", "0",
            "-L", "15",
            "-x", self.params["index_path"],
            "-U", ",".join(self.params["read_paths"])
        ]

        to_otus = set()

        def stdout_handler(line):
            line = line.decode()

            if line[0] == "#" or line[0] == "@":
                return

            fields = line.split("\t")

            # Bitwise FLAG - 0x4: segment unmapped
            if int(fields[1]) & 0x4 == 4:
                return

            ref_id = fields[2]

            if ref_id == "*":
                return

            # Skip if the p_score does not meet the minimum cutoff.
            if virtool.pathoscope.find_sam_align_score(fields) < 0.01:
                return

            to_otus.add(ref_id)

        self.run_subprocess(command, stdout_handler=stdout_handler)

        self.intermediate["to_otus"] = to_otus

    def generate_isolate_fasta(self):
        """
        Identifies otu hits from the initial default otu mapping.

        """
        fasta_path = os.path.join(self.params["analysis_path"], "isolate_index.fa")

        ref_lengths = dict()

        sequence_otu_map = self.params["sequence_otu_map"]

        # The ids of OTUs whose default sequences had mappings.
        otu_ids = {sequence_otu_map[sequence_id] for sequence_id in self.intermediate["to_otus"]}

        # Get the database documents for the sequences
        with open(fasta_path, "w") as handle:
            # Iterate through each otu id referenced by the hit sequence ids.
            for otu_id in otu_ids:
                otu_version = self.params["manifest"][otu_id]
                _, patched, _ = virtool.db.sync.patch_otu_to_version(self.db, otu_id, otu_version)
                for isolate in patched["isolates"]:
                    for sequence in isolate["sequences"]:
                        handle.write(f">{sequence['_id']}\n{sequence['sequence']}\n")
                        ref_lengths[sequence["_id"]] = len(sequence["sequence"])

        del self.intermediate["to_otus"]

        self.intermediate["ref_lengths"] = ref_lengths

    def build_isolate_index(self):
        """
        Build an index with ``bowtie2-build`` from the FASTA file generated by
        :meth:`Pathoscope.generate_isolate_fasta`.

        """
        command = [
            "bowtie2-build",
            "--threads", str(self.proc),
            os.path.join(self.params["analysis_path"], "isolate_index.fa"),
            os.path.join(self.params["analysis_path"], "isolates")
        ]

        self.run_subprocess(command)

    def map_isolates(self):
        """
        Using ``bowtie2``, map the sample reads to the index built using :meth:`.build_isolate_index`.

        """
        command = [
            "bowtie2",
            "-p", str(self.proc - 1),
            "--no-unal",
            "--local",
            "--score-min", "L,20,1.0",
            "-N", "0",
            "-L", "15",
            "-k", "100",
            "--al", os.path.join(self.params["analysis_path"], "mapped.fastq"),
            "-x", os.path.join(self.params["analysis_path"], "isolates"),
            "-U", ",".join(self.params["read_paths"])
        ]

        with open(os.path.join(self.params["analysis_path"], "to_isolates.vta"), "w") as f:
            def stdout_handler(line, p_score_cutoff=0.01):
                line = line.decode()

                if line[0] == "@" or line == "#":
                    return

                fields = line.split("\t")

                # Bitwise FLAG - 0x4 : segment unmapped
                if int(fields[1]) & 0x4 == 4:
                    return

                ref_id = fields[2]

                if ref_id == "*":
                    return

                p_score = virtool.pathoscope.find_sam_align_score(fields)

                # Skip if the p_score does not meet the minimum cutoff.
                if p_score < p_score_cutoff:
                    return

                f.write(",".join([
                    fields[0],  # read_id
                    ref_id,
                    fields[3],  # pos
                    str(len(fields[9])),  # length
                    str(p_score)
                ]) + "\n")

            self.run_subprocess(command, stdout_handler=stdout_handler)

    def map_subtraction(self):
        """
        Using ``bowtie2``, map the reads that were successfully mapped in :meth:`.map_isolates` to the subtraction host
        for the sample.

        """
        command = [
            "bowtie2",
            "--local",
            "-N", "0",
            "-p", str(self.proc - 1),
            "-x", shlex.quote(self.params["subtraction_path"]),
            "-U", os.path.join(self.params["analysis_path"], "mapped.fastq")
        ]

        to_subtraction = dict()

        def stdout_handler(line):
            line = line.decode()

            if line[0] == "@" or line == "#":
                return

            fields = line.split("\t")

            # Bitwise FLAG - 0x4 : segment unmapped
            if int(fields[1]) & 0x4 == 4:
                return

            # No ref_id assigned.
            if fields[2] == "*":
                return

            to_subtraction[fields[0]] = virtool.pathoscope.find_sam_align_score(fields)

        self.run_subprocess(command, stdout_handler=stdout_handler)

        self.intermediate["to_subtraction"] = to_subtraction

    def subtract_mapping(self):
        subtracted_count = virtool.pathoscope.subtract(
            self.params["analysis_path"],
            self.intermediate["to_subtraction"]
        )

        del self.intermediate["to_subtraction"]

        self.results["subtracted_count"] = subtracted_count

    def pathoscope(self):
        """
        Run the Pathoscope reassignment algorithm. Tab-separated output is written to ``pathoscope.tsv``. Results are
        also parsed and saved to :attr:`intermediate`.

        """
        vta_path = os.path.join(self.params["analysis_path"], "to_isolates.vta")
        reassigned_path = os.path.join(self.params["analysis_path"], "reassigned.vta")

        (
            best_hit_initial_reads,
            best_hit_initial,
            level_1_initial,
            level_2_initial,
            best_hit_final_reads,
            best_hit_final,
            level_1_final,
            level_2_final,
            init_pi,
            pi,
            refs,
            reads
        ) = run_patho(vta_path, reassigned_path)

        read_count = len(reads)

        report = virtool.pathoscope.write_report(
            os.path.join(self.params["analysis_path"], "report.tsv"),
            pi,
            refs,
            read_count,
            init_pi,
            best_hit_initial,
            best_hit_initial_reads,
            best_hit_final,
            best_hit_final_reads,
            level_1_initial,
            level_2_initial,
            level_1_final,
            level_2_final
        )

        self.intermediate["coverage"] = virtool.pathoscope.calculate_coverage(
            reassigned_path,
            self.intermediate["ref_lengths"]
        )

        self.results.update({
            "ready": True,
            "read_count": read_count,
            "diagnosis": list()
        })

        for ref_id, hit in report.items():
            # Get the otu info for the sequence id.
            otu_id = self.params["sequence_otu_map"][ref_id]
            otu_version = self.params["manifest"][otu_id]

            hit["id"] = ref_id

            # Attach "otu" (id, version) to the hit.
            hit["otu"] = {
                "version": otu_version,
                "id": otu_id
            }

            # Get the coverage for the sequence.
            hit_coverage = self.intermediate["coverage"][ref_id]

            # Attach coverage list to hit dict.
            hit["align"] = hit_coverage

            # Calculate coverage and attach to hit.
            hit["coverage"] = round(1 - hit_coverage.count(0) / len(hit_coverage), 3)

            # Calculate depth and attach to hit.
            hit["depth"] = round(sum(hit_coverage) / len(hit_coverage))

            self.results["diagnosis"].append(hit)

    def import_results(self):
        """
        Commits the results to the database. Data includes the output of Pathoscope, final mapped read count,
        and viral genome coverage maps.

        Once the import is complete, :meth:`cleanup_index_files` is called to remove
        any otu indexes that may become unused when this analysis completes.

        """
        analysis_id = self.params["analysis_id"]
        sample_id = self.params["sample_id"]

        try:
            self.db.analyses.update_one({"_id": analysis_id}, {
                "$set": self.results
            })
        except pymongo.errors.DocumentTooLarge:
            with open(os.path.join(self.params["analysis_path"], "pathoscope.json"), "w") as f:
                json_string = json.dumps(self.results)
                f.write(json_string)

            self.db.analyses.update_one({"_id": analysis_id}, {
                "$set": {
                    "diagnosis": "file",
                    "ready": True
                }
            })

        virtool.db.sync.recalculate_algorithm_tags(self.db, sample_id)

        self.dispatch("analyses", "update", [analysis_id])
        self.dispatch("samples", "update", [sample_id])

    def cleanup_indexes(self):
        pass


def run_patho(vta_path, reassigned_path):
    u, nu, refs, reads = virtool.pathoscope.build_matrix(vta_path)

    best_hit_initial_reads, best_hit_initial, level_1_initial, level_2_initial = virtool.pathoscope.compute_best_hit(
        u,
        nu,
        refs,
        reads
    )

    init_pi, pi, _, nu = virtool.pathoscope.em(u, nu, refs, 50, 1e-7, 0, 0)

    best_hit_final_reads, best_hit_final, level_1_final, level_2_final = virtool.pathoscope.compute_best_hit(
        u,
        nu,
        refs,
        reads
    )

    virtool.pathoscope.rewrite_align(u, nu, vta_path, 0.01, reassigned_path)

    return (
        best_hit_initial_reads,
        best_hit_initial,
        level_1_initial,
        level_2_initial,
        best_hit_final_reads,
        best_hit_final,
        level_1_final,
        level_2_final,
        init_pi,
        pi,
        refs,
        reads
    )
