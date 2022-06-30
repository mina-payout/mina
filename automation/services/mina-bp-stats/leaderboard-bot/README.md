**SNARK Work Uptime Data Scoring**

This post is an explanation of the scoring system of the new SNARK-work-based Uptime Tracker, the results of which you can see on the [updated Uptime Leaderboard](http://uptime.minaprotocol.com). The leaderboard is the basis for the [Mina Foundation Delegation Program](https://minaprotocol.com/blog/mina-foundation-delegation-policy).

The uptime scoring system is a service that runs every 20 minutes. In each run, it will use the uptime data uploaded in the last 20 minutes and update the scores accordingly. The V3 algorithm will be using new SNARK-work uptime files to determine the uptime score.

The V3 algorithm works in four stages, every 20 minutes:

**1.       Uptime data verification:**

- At the beginning of processing, in the first stage, the process will download all SNARK-work uptime files that were uploaded to Google Cloud Bucket in the last 20 minutes. 
- Then the process uses a stateless verifier (provided by O(1) Labs) to verify all uptime data files. The verifier tool validates the files and returns state hash and parent state hash for each valid file. The process builds a list of all valid files and respective hashes. Please see below sample data extract of just 5 files from the batch.

![](readme-images/001.png)

**2.       Initial Pre-selection (34% Rule):** Since the process of scoring and verifying logs would take some time (15 mins for submission, 3 min for block creation and 20 minutes for score calculation), we may encounter some short forks and various state hashes that are still getting adopted by the network. Since it is rare to see a state hash adopted by more than 40% of BPs when the blockchain is transient, we poll state hashes adopted by at least 34% of BPs (significant network adoption) to accommodate for a wider set of state hashes as valid submissions, regardless of a BP winning a block.  

The set of state hashes adopted by at least 34% of BPs form the pre-selection. The process first builds a set of unique hashes from data above. Then the set is sorted based on the number of block producers (BPs) that have uploaded one or more files for each hash. Next, the algorithm filters out the hashes that do not have at least 34% of BP uploading the files within the 20min-period.

Below example, 

total number of BP: 379

34% of total number of BP: 128.86

So all the hashes having a number of unique BP above 128.86, uploading files with given hash are considered for the next step. In other words, the set of pre-selected state hashes is further accounted for with other state hashes that are children or grandchildren of the pre-selected state hashes (weight <=2 as described in the Step 3, acrylic graph). This is a way for the scoring system to account for short forks and other side effects of network transitioning.

![](readme-images/002.png)

The 34% pre-selection process will also fetch the result of the previous batch in another set. This step will generate two sets of hashes,  set C and set P.

set C: set C with only good hashes (that have BP count higher than 90 percentile) from current data (02:00 – 02:20 batch)

set P: set of hashes that were the result of the algorithm for previous calculation (01:40-2:00 batch).

**3.       Acyclic Graph:** Create acyclic graph of hashes in set P & C identified in above step. First, hashes from P (Yellow Nodes) along with respective weights calculated in the previous batch are added to the graph. Then hashes from C (red nodes) are added with weight 0. If a hash was already present in P, weight 0 prevails over weight found in P.

Next, all hashes from the graph are added to a queue Q. Then, all remaining hashes from the current batch are added to the graph, with infinity weight (Blue nodes). And a relation is established between graph nodes based on parent-child relation identified in step one. See below image of graph.

![](readme-images/003.png)

**4.     	BFS & Weight calculations:** Starting from hashes in queue, Breadth First Search is started on the graph created above. For each child *c* of a node *n* (being considered on this iteration) are assigned weights equal to *w\_c = min (w\_n + 1, w\_c)* where *w\_n* is the weight of node n and *w\_c* is the previous weight of the child. The result will be all hashes that have non-infinity weights.

The final shortlisted hashes will be the ones that have *weight <= 2*. These hashes are selected as shortlisted ones. And all the BP’s that have uploaded at least one file for any of the hash from the current batch will get one uptime point for the current 20-minute iteration.



**Appendix A.** **(SW Uptime Scoring Algorithm Example)**



**Sample Batch Used**: 2022-06-20T:00:00:00Z to 2022-06-20T00:20:00Z



**1. Listing the Number of Unique state-hash with Number Unique Block Producer Count**



| |**state-hash**|**file\_count**|**unique\_bp**|
| :- | :- | :- | :- |
|0|3NKEqSJaYdmzgs7sZT5WNki5WdE6xo6fsyzmhdyk9uERhpDkmAvE|587|330|
|1|3NK9q7zduxfxUrqn2cL9nnGVRLzSjTofMh8PCRmZJ1wTxduTCJPu|579|320|
|2|3NK6rHZpAAKcvdy6wCgu2CLyW9m3AVQ7jLhQwcAyZrGXSWYkMDfj|527|304|
|3|3NLNKPKYzJzbErhCbBucFfnGExz7VL5aora6QVYXAAsnZRY986BG|262|210|
|4|3NKqXfTc37Dzhtb2gZEzmPvVwgfdBvBWbBJ9jEUzDhU2PUDt7xmD|4|4|
|5|3NLJsvtqTnkHBvwqxGWkXpEN911zUPoXxPFjwvDSbYu6jYWBzFH3|3|3|
|6|3NKbBEgQVb6tRXqpj44ZtZ88MTroruLjEqgBTc9iNizVt3rVfUvQ|1|1|
|7|3NLMV9q7hsAj5BrEKwiMFXp1qCqqzoDgGCMTbABR8GqKUTESLQbn|1|1|


Columns:

`        	  `**state-hash**: list of unique State hash in respective batch

`        	  `**file\_count**: Total submissions for that state-hash

`          	  `**unique\_bp** Number of Unique Block producers for that state-hash
**


**2. Primary Selection for good State-hash Based on 34% Pre-selection.**



We select the good state hash from the above table based on at least 34% BPs submitted that state hash among the total BPs.



Total Unique BPs in given batch: **463**

34% Of the Total Unique BPs: **157.42**



**List of good state hashes selected from 34% Pre-selection:**

| |**state-hash**|**file\_count**|**unique\_bp**|
| :- | :- | :- | :- |
|0|3NKEqSJaYdmzgs7sZT5WNki5WdE6xo6fsyzmhdyk9uERhpDkmAvE|587|330|
|1|3NK9q7zduxfxUrqn2cL9nnGVRLzSjTofMh8PCRmZJ1wTxduTCJPu|579|320|
|2|3NK6rHZpAAKcvdy6wCgu2CLyW9m3AVQ7jLhQwcAyZrGXSWYkMDfj|527|304|
|3|3NLNKPKYzJzbErhCbBucFfnGExz7VL5aora6QVYXAAsnZRY986BG|262|210|
`                             	 `**(Table of 34% based state-hash selection)**





Next step,



Our next step will be creating a queue based on previous batch v3 results with **their weights** and current batch 34% criteria result with default weight of **0.** 
**


**3) Creating the Queue List includes the following:**

`        	`previous Batch result: empty

`        	`Current Batch: List of Above table 34%



**queue list :**

['3NKEqSJaYdmzgs7sZT5WNki5WdE6xo6fsyzmhdyk9uERhpDkmAvE',

` `'3NK9q7zduxfxUrqn2cL9nnGVRLzSjTofMh8PCRmZJ1wTxduTCJPu',

` `'3NK6rHZpAAKcvdy6wCgu2CLyW9m3AVQ7jLhQwcAyZrGXSWYkMDfj',

` `'3NLNKPKYzJzbErhCbBucFfnGExz7VL5aora6QVYXAAsnZRY986BG'

]
**


**4) Running the BFS on the given Batch using Queue List and updating the weights:**
**


![](readme-images/004.png)

![](readme-images/005.png)

![](readme-images/006.png)

![](readme-images/007.png)

![](readme-images/008.png)

![](readme-images/009.png)

![](readme-images/010.png)

![](readme-images/011.png)

![](readme-images/012.png)
**

**

**


**5) After Completion of BFS we have state hash with their respective weights**
**


| |**state-hash**|**weights**|
| :- | :- | :- |
|0|3NKEqSJaYdmzgs7sZT5WNki5WdE6xo6fsyzmhdyk9uERhpDkmAvE|0|
|1|3NK9q7zduxfxUrqn2cL9nnGVRLzSjTofMh8PCRmZJ1wTxduTCJPu|0|
|2|3NK6rHZpAAKcvdy6wCgu2CLyW9m3AVQ7jLhQwcAyZrGXSWYkMDfj|0|
|3|3NLNKPKYzJzbErhCbBucFfnGExz7VL5aora6QVYXAAsnZRY986BG|0|
|4|3NLMV9q7hsAj5BrEKwiMFXp1qCqqzoDgGCMTbABR8GqKUTESLQbn|1|
|5|3NLJsvtqTnkHBvwqxGWkXpEN911zUPoXxPFjwvDSbYu6jYWBzFH3|1|
|6|3NKbBEgQVb6tRXqpj44ZtZ88MTroruLjEqgBTc9iNizVt3rVfUvQ|9999|
|7|3NKqXfTc37Dzhtb2gZEzmPvVwgfdBvBWbBJ9jEUzDhU2PUDt7xmD|9999|

**6) Final Selection:** 

We will shortlist the state-hash based on the weights less than or equal to 2 (w<=2).
**


| |**State-hash**|**weights**|
| :- | :- | :- |
|0|3NKEqSJaYdmzgs7sZT5WNki5WdE6xo6fsyzmhdyk9uERhpDkmAvE|0|
|1|3NK9q7zduxfxUrqn2cL9nnGVRLzSjTofMh8PCRmZJ1wTxduTCJPu|0|
|2|3NK6rHZpAAKcvdy6wCgu2CLyW9m3AVQ7jLhQwcAyZrGXSWYkMDfj|0|
|3|3NLNKPKYzJzbErhCbBucFfnGExz7VL5aora6QVYXAAsnZRY986BG|0|
|4|3NLMV9q7hsAj5BrEKwiMFXp1qCqqzoDgGCMTbABR8GqKUTESLQbn|1|
|5|3NLJsvtqTnkHBvwqxGWkXpEN911zUPoXxPFjwvDSbYu6jYWBzFH3|1|
`   `**(Table with Final Selected state-hash Based on V3 Scoring Algorithm)**

**Leaderboard UI changes**

The UI will be updated to reflect both sidecar and SNARK work uptime score on two tabs on the same page. Please see the screenshots below.

**Screenshot for Sidecar data:**

![](readme-images/013.png)

**SNARK work data:**

![](readme-images/014.png)

**Score calculation:**

The process of calculating the uptime score described above runs every 20 minutes (for SNARK work 20 vs 10 minutes for Sidecar). In each iteration, if there are one or more files uploaded by a BP, with shortlisted state hash, the BP gets only one point for that 20 minute iteration. The system will keep calculating uptime points at each 20 minute iteration. 

The UI displays the score based on last points earned in 90 days for SNARK work. The total successful 20 minute iterations performed over the last 90 days are considered as total surveys. So max 20 minutes iterations in 90 days can be 6480. And the number of points can be gained by a BP over 90 days. 
