import asyncio

from app.agents.reviewer_agent import ReviewerAgent


async def main():

    reviewer = ReviewerAgent()

    result = await reviewer.generate(
        user_prompt="""
Problem:
Find the maximum subarray sum.

Candidate Solution:

Algorithm:
Kadane's Algorithm

Code:

int maxSubArray(vector<int>& nums){
    int best = nums[0];
    int cur = nums[0];

    for(int i=1;i<nums.size();i++){
        cur=max(nums[i],cur+nums[i]);
        best=max(best,cur);
    }

    return best;
}
"""
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())